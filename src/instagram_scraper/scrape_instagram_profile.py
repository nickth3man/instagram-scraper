# Copyright (c) 2026 Nicolas Alexander
"""Scrape an Instagram profile into JSON and CSV artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import instaloader
from instaloader import Profile
from instaloader.exceptions import InstaloaderException

DEFAULT_DATA_DIR_FALLBACK = "data"


@dataclass(frozen=True)
class _CommentRecord:
    row: dict[str, str | None]
    post_shortcode: str


def comment_to_dict(comment: Any, parent_id: int | None = None) -> dict[str, str | None]:
    """Convert an Instaloader comment object into a serializable row."""
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
        "comment_like_count": _optional_int_text(getattr(comment, "likes_count", None)),
        "owner_username": owner_username,
        "owner_id": str(owner_id) if owner_id is not None else None,
    }


def _optional_int_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True, help="Instagram username to scrape")
    return parser.parse_args()


def _output_dir(username: str) -> Path:
    data_dir = Path(os.getenv("INSTAGRAM_DATA_DIR", DEFAULT_DATA_DIR_FALLBACK))
    return data_dir / username


def _collect_comments(post: Any) -> tuple[list[dict[str, str | None]], str | None]:
    comments: list[dict[str, str | None]] = []
    try:
        for comment in post.get_comments():
            comments.append(_comment_row(comment, post.shortcode))
            for answer in list(getattr(comment, "answers", [])):
                comments.append(_comment_row(answer, post.shortcode, parent_id=comment.id))
    except InstaloaderException as exc:
        return comments, str(exc)
    return comments, None


def _comment_row(
    comment: Any,
    post_shortcode: str,
    parent_id: int | None = None,
) -> dict[str, str | None]:
    row = comment_to_dict(comment, parent_id=parent_id)
    row["post_shortcode"] = post_shortcode
    return row


def _iter_post_rows(profile: Profile, username: str) -> tuple[list[dict[str, Any]], list[dict[str, str | None]], list[dict[str, str]]]:
    posts: list[dict[str, Any]] = []
    flat_comments: list[dict[str, str | None]] = []
    extraction_errors: list[dict[str, str]] = []
    for post in profile.get_posts():
        post_comments, extraction_error = _collect_comments(post)
        if extraction_error and post.comments != 0:
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


def _write_posts_csv(posts_csv_path: Path, posts: Iterable[dict[str, Any]]) -> None:
    fieldnames = [
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
    with posts_csv_path.open("w", newline="", encoding="utf-8") as posts_file:
        writer = csv.DictWriter(posts_file, fieldnames=fieldnames)
        writer.writeheader()
        for post in posts:
            writer.writerow({key: post[key] for key in fieldnames})


def _write_comments_csv(
    comments_csv_path: Path,
    comments: Iterable[dict[str, str | None]],
) -> None:
    fieldnames = [
        "post_shortcode",
        "id",
        "parent_id",
        "created_at_utc",
        "text",
        "comment_like_count",
        "owner_username",
        "owner_id",
    ]
    with comments_csv_path.open("w", newline="", encoding="utf-8") as comments_file:
        writer = csv.DictWriter(comments_file, fieldnames=fieldnames)
        writer.writeheader()
        for comment in comments:
            writer.writerow(comment)


def main() -> None:
    """Scrape a single Instagram profile and write the resulting files."""
    args = _parse_args()
    target_username = args.username
    started_at = datetime.now(UTC)
    output_dir = _output_dir(target_username)
    output_dir.mkdir(parents=True, exist_ok=True)
    loader = instaloader.Instaloader(
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
    profile = Profile.from_username(loader.context, target_username)
    all_posts, flat_comments, extraction_errors = _iter_post_rows(profile, target_username)
    finished_at = datetime.now(UTC)

    dataset = {
        "target_profile": target_username,
        "source_url": f"https://www.instagram.com/{target_username}/?hl=en",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "posts_total": len(all_posts),
        "comments_total": len(flat_comments),
        "errors_count": len(extraction_errors),
        "posts": all_posts,
    }
    dataset_path = output_dir / "instagram_dataset.json"
    dataset_path.write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    posts_csv_path = output_dir / "posts.csv"
    _write_posts_csv(posts_csv_path, all_posts)
    comments_csv_path = output_dir / "comments.csv"
    _write_comments_csv(comments_csv_path, flat_comments)

    summary = {
        "profile": target_username,
        "posts_extracted": len(all_posts),
        "comments_extracted": len(flat_comments),
        "errors_count": len(extraction_errors),
        "generated_at_utc": finished_at.isoformat(),
        "files": {
            "dataset_json": str(dataset_path),
            "posts_csv": str(posts_csv_path),
            "comments_csv": str(comments_csv_path),
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "posts": len(all_posts),
                "comments": len(flat_comments),
                "errors": len(extraction_errors),
            },
        )
        + "\n",
    )


if __name__ == "__main__":
    main()
