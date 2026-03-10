# Copyright (c) 2026
"""Scrape an Instagram profile into JSON and CSV artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

import instaloader
from instaloader import Profile
from instaloader.exceptions import InstaloaderException

from instagram_scraper.infrastructure.files import atomic_write_text
from instagram_scraper.infrastructure.logging import get_logger

DEFAULT_DATA_DIR_FALLBACK = "data"

# CSV fieldnames extracted to constants to avoid duplication
POSTS_CSV_FIELDNAMES = [
    "shortcode",
    "post_url",
    "date_utc",
    "caption",
    "likes",
    "comments_count_reported",
    "is_video",
    "typename",
    "owner_username",
]

COMMENTS_CSV_FIELDNAMES = [
    "post_shortcode",
    "id",
    "parent_id",
    "created_at_utc",
    "text",
    "comment_like_count",
    "owner_username",
    "owner_id",
]


@dataclass(frozen=True, slots=True)
class _ScrapeResults:
    posts: list[dict[str, object]]
    flat_comments: list[dict[str, int | str | None]]
    extraction_errors: list[dict[str, str]]


def comment_to_dict(
    comment: object,
    parent_id: int | None = None,
) -> dict[str, int | str | None]:
    """Convert an Instaloader comment object into a serializable row.

    Returns
    -------
    dict[str, int | str | None]
        A JSON-serializable representation of the comment.

    """
    # Instaloader gives us rich Python objects. The scraper output needs plain
    # strings, numbers, and `None` so it can be saved as JSON and CSV.
    owner = getattr(comment, "owner", None)
    owner_username = getattr(owner, "username", None)
    owner_id = getattr(owner, "userid", None)
    created_at = getattr(comment, "created_at_utc", None)
    created_at_iso = created_at.isoformat() if created_at is not None else None
    return {
        "id": str(getattr(comment, "id", "")),
        "parent_id": str(parent_id) if parent_id is not None else None,
        "created_at_utc": created_at_iso,
        "text": getattr(comment, "text", None),
        "comment_like_count": getattr(comment, "likes_count", None),
        "owner_username": owner_username,
        "owner_id": str(owner_id) if owner_id is not None else None,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--username",
        required=True,
        help="Instagram username to scrape",
    )
    return parser.parse_args()


def _get_output_dir(username: str) -> Path:
    # Keep all files for one Instagram account inside the same folder.
    data_dir = Path(os.getenv("INSTAGRAM_DATA_DIR", DEFAULT_DATA_DIR_FALLBACK))
    return data_dir / username


def _collect_comments(
    post: instaloader.Post,
) -> tuple[list[dict[str, int | str | None]], str | None]:
    comments: list[dict[str, int | str | None]] = []
    try:
        for comment in post.get_comments():
            # Store the top-level comment first.
            comments.append(_comment_row(comment, post.shortcode))
            comments.extend(
                # Replies become extra rows linked back to the parent comment.
                _comment_row(answer, post.shortcode, parent_id=comment.id)
                for answer in list(getattr(comment, "answers", []))
            )
    except InstaloaderException as exc:
        return comments, str(exc)
    return comments, None


def _comment_row(
    comment: object,
    post_shortcode: str,
    parent_id: int | None = None,
) -> dict[str, int | str | None]:
    row = comment_to_dict(comment, parent_id=parent_id)
    row["post_shortcode"] = post_shortcode
    return row


def _iter_post_rows(
    loader: instaloader.Instaloader,
    profile: Profile,
    username: str,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, int | str | None]],
    list[dict[str, str]],
]:
    posts: list[dict[str, object]] = []
    flat_comments: list[dict[str, int | str | None]] = []
    extraction_errors: list[dict[str, str]] = []
    for post in profile.get_posts():
        quota_messages = getattr(loader.context, "quotamessages", None)
        if quota_messages:
            get_logger(__name__).warning(
                "rate limit warning",
                extra={"quota_message": quota_messages[-1]},
            )
        post_comments, extraction_error = _collect_comments(post)
        if extraction_error and post.comments != 0:
            # If Instagram reported comments but we failed to fetch them, record
            # the failure and skip this post instead of writing partial data.
            extraction_errors.append(
                {
                    "post_shortcode": post.shortcode,
                    "error": extraction_error,
                },
            )
            continue
        post_row = {
            "shortcode": post.shortcode,
            "post_url": f"https://www.instagram.com/p/{post.shortcode}/",
            "date_utc": post.date_utc.isoformat(),
            "caption": post.caption,
            "likes": post.likes,
            "comments_count_reported": post.comments,
            "is_video": post.is_video,
            "typename": post.typename,
            "owner_username": username,
            "comments": post_comments,
        }
        posts.append(post_row)
        flat_comments.extend(post_comments)
    return posts, flat_comments, extraction_errors


def _write_posts_csv(posts_csv_path: Path, posts: Iterable[dict[str, object]]) -> None:
    with posts_csv_path.open("w", newline="", encoding="utf-8") as posts_file:
        writer = csv.DictWriter(posts_file, fieldnames=POSTS_CSV_FIELDNAMES)
        writer.writeheader()
        for post in posts:
            # Only write the simple summary columns here. The nested `comments`
            # list stays in the JSON file instead.
            writer.writerow({key: post[key] for key in POSTS_CSV_FIELDNAMES})


def _write_comments_csv(
    comments_csv_path: Path,
    comments: Iterable[dict[str, int | str | None]],
) -> None:
    with comments_csv_path.open("w", newline="", encoding="utf-8") as comments_file:
        writer = csv.DictWriter(comments_file, fieldnames=COMMENTS_CSV_FIELDNAMES)
        writer.writeheader()
        for comment in comments:
            writer.writerow(comment)


def _create_instaloader() -> instaloader.Instaloader:
    """Create and configure an Instaloader instance for metadata scraping.

    Returns
    -------
    instaloader.Instaloader
        Configured instance with media downloads disabled.

    """
    return instaloader.Instaloader(
        dirname_pattern="{target}",
        filename_pattern="{shortcode}",
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
        compress_json=False,
        quiet=True,
    )


def _create_dataset_dict(
    target_username: str,
    started_at: datetime,
    finished_at: datetime,
    results: _ScrapeResults,
) -> dict[str, object]:
    """Create the dataset dictionary for JSON output.

    Parameters
    ----------
    target_username : str
        Instagram username being scraped.
    started_at : datetime
        Scraping start time.
    finished_at : datetime
        Scraping completion time.
    results : _ScrapeResults
        Collected post, comment, and extraction error data.

    Returns
    -------
    dict[str, object]
        Dataset dictionary ready for JSON serialization.

    """
    return {
        "target_profile": target_username,
        "source_url": f"https://www.instagram.com/{target_username}/?hl=en",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "posts_total": len(results.posts),
        "comments_total": len(results.flat_comments),
        "errors_count": len(results.extraction_errors),
        "posts": results.posts,
    }


def _create_summary_dict(
    target_username: str,
    finished_at: datetime,
    output_dir: Path,
    results: _ScrapeResults,
) -> dict[str, object]:
    """Create a summary dictionary for quick status checking.

    Parameters
    ----------
    target_username : str
        Instagram username being scraped.
    finished_at : datetime
        Scraping completion time.
    output_dir : Path
        Directory where output files were written.
    results : _ScrapeResults
        Collected post, comment, and extraction error data.

    Returns
    -------
    dict[str, object]
        Summary dictionary ready for JSON serialization.

    """
    dataset_path = output_dir / "instagram_dataset.json"
    posts_csv_path = output_dir / "posts.csv"
    comments_csv_path = output_dir / "comments.csv"

    return {
        "profile": target_username,
        "posts_extracted": len(results.posts),
        "comments_extracted": len(results.flat_comments),
        "errors_count": len(results.extraction_errors),
        "generated_at_utc": finished_at.isoformat(),
        "files": {
            "dataset_json": str(dataset_path),
            "posts_csv": str(posts_csv_path),
            "comments_csv": str(comments_csv_path),
        },
    }


def _write_outputs(
    output_dir: Path,
    dataset: dict[str, object],
    all_posts: list[dict[str, object]],
    flat_comments: list[dict[str, int | str | None]],
) -> None:
    """Write all output files to disk.

    Parameters
    ----------
    output_dir : Path
        Directory to write output files.
    dataset : dict[str, object]
        Dataset dictionary to write as JSON.
    all_posts : list[dict[str, object]]
        Post data to write as CSV.
    flat_comments : list[dict[str, int | str | None]]
        Comment data to write as CSV.

    """
    dataset_path = output_dir / "instagram_dataset.json"
    atomic_write_text(
        dataset_path,
        json.dumps(dataset, indent=2, ensure_ascii=False),
    )

    posts_csv_path = output_dir / "posts.csv"
    _write_posts_csv(posts_csv_path, all_posts)

    comments_csv_path = output_dir / "comments.csv"
    _write_comments_csv(comments_csv_path, flat_comments)


def run_profile_scrape(*, username: str, output_dir: Path) -> dict[str, object]:
    """Scrape a single Instagram profile and write the resulting files.

    Parameters
    ----------
    username : str
        The Instagram username to scrape.
    output_dir : Path
        Directory to write output files.

    Returns
    -------
    dict[str, object]
        Summary of the scrape operation.

    """
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(UTC)

    loader = _create_instaloader()
    profile = Profile.from_username(loader.context, username)
    all_posts, flat_comments, extraction_errors = _iter_post_rows(
        loader,
        profile,
        username,
    )
    finished_at = datetime.now(UTC)
    results = _ScrapeResults(
        posts=all_posts,
        flat_comments=flat_comments,
        extraction_errors=extraction_errors,
    )

    dataset = _create_dataset_dict(
        username,
        started_at,
        finished_at,
        results,
    )
    _write_outputs(output_dir, dataset, all_posts, flat_comments)

    summary = _create_summary_dict(
        username,
        finished_at,
        output_dir,
        results,
    )
    atomic_write_text(
        output_dir / "summary.json",
        json.dumps(summary, indent=2),
    )

    return {
        "posts": len(all_posts),
        "comments": len(flat_comments),
        "errors": len(extraction_errors),
    }


def main() -> None:
    """Scrape a single Instagram profile and write the resulting files."""
    args = _parse_args()
    target_username = args.username
    output_dir = _get_output_dir(target_username)

    result = run_profile_scrape(
        username=target_username,
        output_dir=output_dir,
    )

    sys.stdout.write(
        json.dumps(result) + "\n",
    )


if __name__ == "__main__":
    main()
