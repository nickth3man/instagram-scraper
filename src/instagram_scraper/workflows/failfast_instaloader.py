# Copyright (c) 2026
"""Fail-fast Instaloader scraping for URL batches."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from instaloader import Post
from instaloader.exceptions import (
    BadResponseException,
    InstaloaderException,
    TooManyRequestsException,
)

from instagram_scraper.infrastructure.files import (
    append_csv_row,
    atomic_write_text,
    ensure_csv_with_header,
    load_json_dict,
)
from instagram_scraper.workflows._instaloader_failfast import (
    FailFastTooManyRequestsRateController,
    build_failfast_instaloader,
    checkpoint_path,
    cookie_dict,
    load_cookie_header,
)
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
    output_dir: Path
    start_index: int
    limit: int | None
    download_media: bool
    should_reset_output: bool


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
    return Config(
        input_path=args.input,
        output_dir=args.output_dir,
        start_index=args.start_index,
        limit=args.limit,
        download_media=args.download_media,
        should_reset_output=args.reset_output,
    )


def run(cfg: Config) -> dict[str, object]:
    """Run fail-fast scraping for the configured URL batch.

    Returns
    -------
        Summary dictionary describing the processed range and written artifacts.
    """
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_outputs(cfg.output_dir, reset_output=cfg.should_reset_output)
    urls = _load_urls(cfg.input_path)
    cookies = cookie_dict(load_cookie_header())
    username = cookies.get("ds_user_id", "session")
    loader = build_failfast_instaloader(
        dirname_pattern=str(cfg.output_dir / "downloads" / "{target}"),
        download_media=cfg.download_media,
        rate_controller=FailFastTooManyRequestsRateController,
    )
    loader.load_session(username, cookies)

    end_index = _end_index(cfg.start_index, cfg.limit, len(urls))
    processed = 0
    for index in range(cfg.start_index, end_index):
        processed += _process_url(
            index=index,
            post_url=urls[index],
            cfg=cfg,
            loader=loader,
        )
        _save_checkpoint(cfg.output_dir, next_index=index + 1, processed=processed)

    return _summary(cfg.output_dir, cfg.start_index, end_index, processed)


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
    payload = load_json_dict(input_path)
    if payload is None:
        payload = cast(
            "dict[str, object]",
            json.loads(input_path.read_text(encoding="utf-8")),
        )
    raw_urls = payload.get("urls")
    if not isinstance(raw_urls, list):
        message = "tool dump must contain a urls list"
        raise TypeError(message)
    return [url for url in raw_urls if isinstance(url, str)]


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
    shortcode = post_url.rstrip("/").split("/")[-1]
    try:
        post = Post.from_shortcode(loader.context, shortcode)
        _write_post_row(post, post_url, cfg.output_dir)
        _write_comment_rows(post, cfg.output_dir)
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
            cfg.output_dir / "errors.csv",
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
