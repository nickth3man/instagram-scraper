# Copyright (c) 2026
"""Fail-fast Instaloader scraping for URL batches."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

from instaloader import Post
from instaloader.exceptions import (
    BadResponseException,
    InstaloaderException,
    TooManyRequestsException,
)

from instagram_scraper.config import OutputConfig, ScraperConfig
from instagram_scraper.error_codes import ErrorCode
from instagram_scraper.exceptions import InstagramError
from instagram_scraper.infrastructure.files import (
    append_csv_row,
    atomic_write_text,
    ensure_csv_with_header,
)
from instagram_scraper.workflows._instaloader_failfast import (
    FailFastTooManyRequestsRateController,
    build_failfast_instaloader,
    checkpoint_path,
    cookie_dict,
    load_cookie_header,
)
from instagram_scraper.workflows._workflow_inputs import load_tool_dump_urls
from instagram_scraper.workflows.profile import (
    COMMENTS_CSV_FIELDNAMES,
    POSTS_CSV_FIELDNAMES,
    comment_to_dict,
)

if TYPE_CHECKING:
    from instaloader import Instaloader

ERROR_HEADER = ["index", "post_url", "shortcode", "stage", "error"]
_DEFAULT_INPUT_PATH = Path("data") / "believerofbuckets" / "tool_dump.json"
_DEFAULT_OUTPUT_DIR = Path("data") / "believerofbuckets"


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration for fail-fast URL scraping."""

    input_path: Path
    scraper: ScraperConfig
    start_index: int
    download_media: bool


__all__ = ["Config", "main", "parse_args", "run"]


def parse_args() -> Config:
    """Parse command-line arguments into a workflow config.

    Returns
    -------
        Parsed runtime configuration.
    """
    parser = argparse.ArgumentParser(
        description="Fail-fast Instaloader scrape for batch processing",
    )
    parser.add_argument("--input", type=Path, default=_DEFAULT_INPUT_PATH)
    parser.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--download-media", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    args = parser.parse_args()
    if args.start_index < 0:
        parser.error("--start-index must be non-negative")
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be non-negative")
    return Config(
        input_path=args.input,
        scraper=ScraperConfig(
            output=OutputConfig(
                output_dir=args.output_dir,
                should_reset_output=args.reset_output,
            ),
            limit=args.limit,
        ),
        start_index=args.start_index,
        download_media=args.download_media,
    )


def run(cfg: Config) -> dict[str, object]:
    """Run fail-fast scraping for the configured URL batch.

    Returns
    -------
        Summary dictionary describing the processed range and written artifacts.
    """
    output_dir = cfg.scraper.output.output_dir
    cfg.scraper.output.output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_outputs(output_dir, reset_output=cfg.scraper.output.should_reset_output)
    urls = _load_urls(cfg.input_path)
    cookies = cookie_dict(load_cookie_header())
    username = cookies.get("ds_user_id", "session")
    loader = build_failfast_instaloader(
        dirname_pattern=str(output_dir / "downloads" / "{target}"),
        download_media=cfg.download_media,
        rate_controller=FailFastTooManyRequestsRateController,
    )
    loader.load_session(username, cookies)

    end_index = _end_index(cfg.start_index, cfg.scraper.limit, len(urls))
    processed = 0
    for index in range(cfg.start_index, end_index):
        processed += _process_url(
            index=index,
            post_url=urls[index],
            cfg=cfg,
            loader=loader,
        )
        _save_checkpoint(output_dir, next_index=index + 1, processed=processed)

    return _summary(output_dir, cfg.start_index, end_index, processed)


def main() -> int:
    """Run the fail-fast scraper CLI and emit a JSON summary.

    Returns
    -------
        Process exit code.
    """
    summary = run(parse_args())
    sys.stdout.write(json.dumps(summary) + "\n")
    return 0


def _load_urls(input_path: Path) -> list[str]:
    try:
        return load_tool_dump_urls(input_path)
    except InstagramError as exc:
        if exc.code == ErrorCode.PARSE_INVALID_SHAPE:
            message = "tool dump must contain a urls list"
            raise InstagramError(message, code=ErrorCode.PARSE_INVALID_SHAPE) from exc
        raise


def _ensure_outputs(output_dir: Path, *, reset_output: bool) -> None:
    ensure_csv_with_header(
        output_dir / "posts.csv",
        POSTS_CSV_FIELDNAMES,
        reset=reset_output,
    )
    ensure_csv_with_header(
        output_dir / "comments.csv",
        COMMENTS_CSV_FIELDNAMES,
        reset=reset_output,
    )
    ensure_csv_with_header(output_dir / "errors.csv", ERROR_HEADER, reset=reset_output)


def _end_index(start_index: int, limit: int | None, urls_count: int) -> int:
    return urls_count if limit is None else min(urls_count, start_index + limit)


def _process_url(
    *,
    index: int,
    post_url: str,
    cfg: Config,
    loader: Instaloader,
) -> int:
    shortcode = _shortcode_from_url(post_url)
    try:
        post = Post.from_shortcode(loader.context, shortcode)
        output_dir = cfg.scraper.output.output_dir
        _write_post_row(post, post_url, output_dir)
        _write_comment_rows(post, output_dir)
        if cfg.download_media:
            loader.download_post(post, target=post.owner_username)
    except (
        BadResponseException,
        InstaloaderException,
        TooManyRequestsException,
        KeyError,
        ValueError,
    ) as exc:
        append_csv_row(
            cfg.scraper.output.output_dir / "errors.csv",
            ERROR_HEADER,
            {
                "index": index,
                "post_url": post_url,
                "shortcode": shortcode,
                "stage": "extract_post",
                "error": type(exc).__name__,
            },
        )
        return 0
    return 1


def _shortcode_from_url(post_url: str) -> str:
    parts = [part for part in urlsplit(post_url).path.split("/") if part]
    shortcode = parts[-1] if parts else ""
    if shortcode:
        return shortcode
    message = f"Unable to extract shortcode from {post_url}"
    raise InstagramError(message, code=ErrorCode.INPUT_INVALID_URL)


def _write_post_row(post: Post, post_url: str, output_dir: Path) -> None:
    append_csv_row(
        output_dir / "posts.csv",
        POSTS_CSV_FIELDNAMES,
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


def _write_comment_rows(post: Post, output_dir: Path) -> None:
    for comment in post.get_comments():
        append_csv_row(
            output_dir / "comments.csv",
            COMMENTS_CSV_FIELDNAMES,
            _comment_row(comment, post_shortcode=post.shortcode),
        )
        for answer in comment.answers:
            append_csv_row(
                output_dir / "comments.csv",
                COMMENTS_CSV_FIELDNAMES,
                _comment_row(
                    answer,
                    post_shortcode=post.shortcode,
                    parent_id=comment.id,
                ),
            )


def _comment_row(
    comment: object,
    *,
    post_shortcode: str,
    parent_id: int | None = None,
) -> dict[str, object]:
    row = comment_to_dict(comment, parent_id=parent_id)
    row["post_shortcode"] = post_shortcode
    return cast("dict[str, object]", row)


def _save_checkpoint(output_dir: Path, *, next_index: int, processed: int) -> None:
    atomic_write_text(
        checkpoint_path(output_dir),
        json.dumps({"next_index": next_index, "processed": processed}, indent=2),
    )


def _summary(
    output_dir: Path,
    start_index: int,
    end_index: int,
    processed: int,
) -> dict[str, object]:
    return {
        "start_index": start_index,
        "end_index_exclusive": end_index,
        "processed": processed,
        "checkpoint": str(checkpoint_path(output_dir)),
        "posts_csv": str(output_dir / "posts.csv"),
        "comments_csv": str(output_dir / "comments.csv"),
        "errors_csv": str(output_dir / "errors.csv"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
