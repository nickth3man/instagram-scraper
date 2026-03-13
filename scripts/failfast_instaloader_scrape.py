# Copyright (c) 2024-present. Author holds all rights.
"""Fail-fast Instaloader scrape script for batch processing Instagram posts.

This script provides a fail-fast approach to scraping Instagram posts using
Instaloader, designed to stop immediately on rate limits (429) rather than
retrying. It processes URLs from a tool dump JSON file and outputs results
to CSV files.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import override

from instaloader import Instaloader, Post
from instaloader.exceptions import (
    BadResponseException,
    TooManyRequestsException,
)
from instaloader.instaloadercontext import RateController

logger = logging.getLogger(__name__)

_URLS_LIST_REQUIRED = "tool dump must contain a urls list"
_FAIL_FAST_429 = "fail-fast-429:{}"


@dataclass(frozen=True)
class CsvFieldConfig:
    """Configuration for CSV field names."""

    post_fields: list[str]
    comment_fields: list[str]
    error_fields: list[str]


@dataclass(frozen=True)
class ProcessContext:
    """Context for processing a single post."""

    post: Post
    post_url: str
    output_dir: Path
    field_config: CsvFieldConfig
    loader: Instaloader
    download_media: bool


class FailFastRateController(RateController):
    """Rate controller that immediately fails on 429 responses.

    Unlike the default RateController which waits and retries on rate limits,
    this controller raises TooManyRequestsException immediately for fail-fast
    behavior during batch processing.
    """

    @override
    def handle_429(self, query_type: str) -> None:
        """Handle a 429 Too Many Requests response by immediately failing.

        Args:
            query_type: Type of query that triggered the rate limit.

        Raises
        ------
        TooManyRequestsException
            Always raised to signal rate limit hit.
        """
        msg = _FAIL_FAST_429.format(query_type)
        raise TooManyRequestsException(msg)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
        Parsed namespace containing input, output-dir, start-index, limit,
        download-media, and reset-output options.
    """
    parser = argparse.ArgumentParser(
        description="Fail-fast Instaloader scrape for batch processing",
    )
    parser.add_argument("--input", default="data/believerofbuckets/tool_dump.json")
    parser.add_argument("--output-dir", default="data/believerofbuckets")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--download-media", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    return parser.parse_args()


def load_cookie_header() -> str:
    """Load Instagram cookie header from .env file.

    Returns
    -------
        Cookie header string if found, empty string otherwise.
    """
    env_path = Path(".env")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("IG_COOKIE_HEADER="):
            return line.split("=", 1)[1]
    return ""


def cookie_dict(cookie_header: str) -> dict[str, str]:
    """Parse cookie header string into a dictionary.

    Args:
        cookie_header: Raw cookie header string from browser.

    Returns
    -------
        Dictionary mapping cookie names to values.
    """
    return {
        key.strip(): value.strip()
        for part in cookie_header.split(";")
        if "=" in part
        for key, value in [part.split("=", 1)]
    }


def post_rows_path(output_dir: Path) -> Path:
    """Get path to posts CSV file.

    Args:
        output_dir: Base output directory.

    Returns
    -------
        Path to posts.csv file.
    """
    return output_dir / "posts.csv"


def comment_rows_path(output_dir: Path) -> Path:
    """Get path to comments CSV file.

    Args:
        output_dir: Base output directory.

    Returns
    -------
        Path to comments.csv file.
    """
    return output_dir / "comments.csv"


def error_rows_path(output_dir: Path) -> Path:
    """Get path to errors CSV file.

    Args:
        output_dir: Base output directory.

    Returns
    -------
        Path to errors.csv file.
    """
    return output_dir / "errors.csv"


def checkpoint_path(output_dir: Path) -> Path:
    """Get path to checkpoint JSON file.

    Args:
        output_dir: Base output directory.

    Returns
    -------
        Path to checkpoint_instaloader.json file.
    """
    return output_dir / "checkpoint_instaloader.json"


def ensure_headers(
    path: Path,
    fieldnames: list[str],
    *,
    reset: bool = False,
) -> None:
    """Ensure CSV file exists with proper headers.

    Args:
        path: Path to CSV file.
        fieldnames: List of column names for the CSV header.
        reset: If True, delete existing file before creating new one.
    """
    if reset and path.exists():
        path.unlink()
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()


def append_row(
    path: Path,
    fieldnames: list[str],
    row: dict[str, object],
) -> None:
    """Append a single row to a CSV file.

    Args:
        path: Path to CSV file.
        fieldnames: List of column names (must match row keys).
        row: Dictionary containing row data.
    """
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writerow(row)


def save_checkpoint(output_dir: Path, next_index: int, processed: int) -> None:
    """Save processing checkpoint to JSON file.

    Args:
        output_dir: Base output directory.
        next_index: Index of next URL to process.
        processed: Count of successfully processed posts.
    """
    checkpoint_path(output_dir).write_text(
        json.dumps({"next_index": next_index, "processed": processed}, indent=2),
        encoding="utf-8",
    )


def _validate_urls(payload: dict[str, object]) -> list[str]:
    """Validate and extract URLs from payload.

    Args:
        payload: Parsed JSON payload from tool dump.

    Returns
    -------
        List of URL strings.

    Raises
    ------
    TypeError
        If urls field is not a list.
    """
    urls = payload.get("urls", [])
    if not isinstance(urls, list):
        raise TypeError(_URLS_LIST_REQUIRED)
    return [str(u) for u in urls if isinstance(u, str)]


def _write_post_row(
    post: Post,
    post_url: str,
    output_dir: Path,
    post_fields: list[str],
) -> None:
    """Write post data to CSV.

    Args:
        post: Instaloader Post object.
        post_url: Original URL for the post.
        output_dir: Output directory for CSV files.
        post_fields: Field names for posts CSV.
    """
    append_row(
        post_rows_path(output_dir),
        post_fields,
        {
            "shortcode": post.shortcode,
            "post_url": post_url,
            "media_id": post.mediaid,
            "date_utc": post.date_utc.isoformat(),
            "caption": post.caption or "",
            "likes": post.likes,
            "comments_count_reported": post.comments,
            "is_video": post.is_video,
            "typename": post.typename,
            "owner_username": post.owner_username,
        },
    )


def _write_comment_rows(
    post: Post,
    output_dir: Path,
    comment_fields: list[str],
) -> None:
    """Write comment data to CSV.

    Args:
        post: Instaloader Post object.
        output_dir: Output directory for CSV files.
        comment_fields: Field names for comments CSV.
    """
    for comment in post.get_comments():
        append_row(
            comment_rows_path(output_dir),
            comment_fields,
            {
                "post_shortcode": post.shortcode,
                "id": str(comment.id),
                "parent_id": "",
                "created_at_utc": comment.created_at_utc.isoformat(),
                "text": comment.text or "",
                "comment_like_count": comment.likes_count,
                "owner_username": comment.owner.username,
                "owner_id": str(comment.owner.userid),
            },
        )
        for answer in comment.answers:
            append_row(
                comment_rows_path(output_dir),
                comment_fields,
                {
                    "post_shortcode": post.shortcode,
                    "id": str(answer.id),
                    "parent_id": str(comment.id),
                    "created_at_utc": answer.created_at_utc.isoformat(),
                    "text": answer.text or "",
                    "comment_like_count": answer.likes_count,
                    "owner_username": answer.owner.username,
                    "owner_id": str(answer.owner.userid),
                },
            )


def _process_post(
    ctx: ProcessContext,
) -> int:
    """Process a single post and write results to CSV.

    Args:
        ctx: Processing context containing post, paths, and configuration.

    Returns
    -------
        Number of posts processed (always 1 on success).
    """
    _write_post_row(
        ctx.post,
        ctx.post_url,
        ctx.output_dir,
        ctx.field_config.post_fields,
    )
    _write_comment_rows(
        ctx.post,
        ctx.output_dir,
        ctx.field_config.comment_fields,
    )
    if ctx.download_media:
        ctx.loader.download_post(ctx.post, target=ctx.post.owner_username)
    return 1


def _setup_field_configs() -> CsvFieldConfig:
    """Create field configuration for CSV files.

    Returns
    -------
        CsvFieldConfig with post, comment, and error field names.
    """
    return CsvFieldConfig(
        post_fields=[
            "shortcode",
            "post_url",
            "media_id",
            "date_utc",
            "caption",
            "likes",
            "comments_count_reported",
            "is_video",
            "typename",
            "owner_username",
        ],
        comment_fields=[
            "post_shortcode",
            "id",
            "parent_id",
            "created_at_utc",
            "text",
            "comment_like_count",
            "owner_username",
            "owner_id",
        ],
        error_fields=["index", "post_url", "shortcode", "stage", "error"],
    )


def _create_instaloader(
    output_dir: Path,
    *,
    download_media: bool,
) -> Instaloader:
    """Create and configure Instaloader instance.

    Args:
        output_dir: Output directory for downloads.
        download_media: Whether to download media files.

    Returns
    -------
        Configured Instaloader instance.
    """
    return Instaloader(
        dirname_pattern=str(output_dir / "downloads" / "{target}"),
        filename_pattern="{shortcode}",
        download_pictures=download_media,
        download_videos=download_media,
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        sleep=False,
        max_connection_attempts=1,
        request_timeout=20.0,
        rate_controller=FailFastRateController,
    )


def _log_result(
    args: argparse.Namespace,
    end_index: int,
    processed: int,
    output_dir: Path,
) -> None:
    """Log final result summary.

    Args:
        args: Parsed command-line arguments.
        end_index: End index of processing.
        processed: Number of successfully processed posts.
        output_dir: Output directory for output files.
    """
    result = {
        "start_index": args.start_index,
        "end_index_exclusive": end_index,
        "processed": processed,
        "checkpoint": str(checkpoint_path(output_dir)),
        "posts_csv": str(post_rows_path(output_dir)),
        "comments_csv": str(comment_rows_path(output_dir)),
        "errors_csv": str(error_rows_path(output_dir)),
    }
    logger.info(json.dumps(result))


def _init_csv_headers(
    output_dir: Path,
    field_config: CsvFieldConfig,
    *,
    reset: bool = False,
) -> None:
    """Initialize CSV files with headers.

    Args:
        output_dir: Output directory for CSV files.
        field_config: Field configuration for CSV files.
        reset: If True, delete existing files before creating new ones.
    """
    ensure_headers(
        post_rows_path(output_dir),
        field_config.post_fields,
        reset=reset,
    )
    ensure_headers(
        comment_rows_path(output_dir),
        field_config.comment_fields,
        reset=reset,
    )
    ensure_headers(
        error_rows_path(output_dir),
        field_config.error_fields,
        reset=reset,
    )


@dataclass(frozen=True)
class ProcessingConfig:
    """Configuration for URL batch processing."""

    urls: list[str]
    start_index: int
    end_index: int
    output_dir: Path
    field_config: CsvFieldConfig
    loader: Instaloader
    download_media: bool


def _process_urls(config: ProcessingConfig) -> int:
    """Process URLs and return count of successful posts.

    Args:
        config: Processing configuration containing all parameters.

    Returns
    -------
        Number of successfully processed posts.
    """
    processed = 0
    for index in range(config.start_index, config.end_index):
        post_url = config.urls[index]
        if not isinstance(post_url, str):
            continue
        shortcode = post_url.rstrip("/").split("/")[-1]
        try:
            post = Post.from_shortcode(config.loader.context, shortcode)
            ctx = ProcessContext(
                post=post,
                post_url=post_url,
                output_dir=config.output_dir,
                field_config=config.field_config,
                loader=config.loader,
                download_media=config.download_media,
            )
            processed += _process_post(ctx)
        except (
            BadResponseException,
            TooManyRequestsException,
            KeyError,
            ValueError,
        ) as exc:
            append_row(
                error_rows_path(config.output_dir),
                config.field_config.error_fields,
                {
                    "index": index,
                    "post_url": post_url,
                    "shortcode": shortcode,
                    "stage": "extract_post",
                    "error": type(exc).__name__,
                },
            )
        save_checkpoint(config.output_dir, index + 1, processed)
    return processed


def main() -> int:
    """Run fail-fast Instaloader scrape.

    Returns
    -------
        Exit code (0 for success, non-zero for errors).
    """
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    urls = _validate_urls(payload)
    field_config = _setup_field_configs()

    _init_csv_headers(output_dir, field_config, reset=args.reset_output)

    cookie_header = load_cookie_header()
    cookies = cookie_dict(cookie_header)
    username = cookies.get("ds_user_id", "session")
    loader = _create_instaloader(output_dir, download_media=args.download_media)
    loader.load_session(username, cookies)

    end_index = min(len(urls), args.start_index + args.limit)
    config = ProcessingConfig(
        urls=urls,
        start_index=args.start_index,
        end_index=end_index,
        output_dir=output_dir,
        field_config=field_config,
        loader=loader,
        download_media=args.download_media,
    )
    processed = _process_urls(config)

    _log_result(args, end_index, processed, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
