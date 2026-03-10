# Copyright (c) 2026
"""I/O and checkpoint helpers for video_downloads."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import TYPE_CHECKING, cast

from instagram_scraper.infrastructure.files import (
    append_csv_row,
    atomic_write_text,
    ensure_csv_with_header,
    load_json_dict,
)
from instagram_scraper.workflows._video_download_types import (
    COMMENTS_SNAPSHOT_HEADER,
    DOWNLOAD_ERROR_HEADER,
    RESETTABLE_OUTPUT_FILENAMES,
    VIDEO_INDEX_HEADER,
    CheckpointState,
    Config,
    _DownloadMetrics,
    _DownloadPaths,
    _PostTarget,
)

if TYPE_CHECKING:
    from pathlib import Path


def _atomic_write_text(path: Path, content: str) -> None:
    atomic_write_text(path, content)


def _ensure_csv(path: Path, header: list[str], *, reset_output: bool) -> None:
    ensure_csv_with_header(path, header, reset=reset_output)


def _append_csv(path: Path, header: list[str], row: dict[str, object]) -> None:
    append_csv_row(path, header, row)


def _checkpoint_file(output_dir: Path) -> Path:
    return output_dir / "videos_checkpoint.json"


def _load_checkpoint(output_dir: Path) -> CheckpointState | None:
    payload = load_json_dict(_checkpoint_file(output_dir))
    return cast("CheckpointState", payload) if payload is not None else None


def _save_checkpoint(output_dir: Path, state: CheckpointState) -> None:
    _atomic_write_text(_checkpoint_file(output_dir), json.dumps(state, indent=2))


def _prepare_output(cfg: Config) -> _DownloadPaths:
    videos_root = cfg.output_dir / "videos"
    videos_root.mkdir(parents=True, exist_ok=True)
    index_csv = cfg.output_dir / "videos_index.csv"
    errors_csv = cfg.output_dir / "videos_errors.csv"
    if cfg.should_reset_output:
        for file_name in RESETTABLE_OUTPUT_FILENAMES:
            path = cfg.output_dir / file_name
            if path.exists():
                path.unlink()
    index_header = list(VIDEO_INDEX_HEADER)
    error_header = list(DOWNLOAD_ERROR_HEADER)
    _ensure_csv(index_csv, index_header, reset_output=cfg.should_reset_output)
    _ensure_csv(errors_csv, error_header, reset_output=cfg.should_reset_output)
    return {
        "videos_root": videos_root,
        "index_csv": index_csv,
        "errors_csv": errors_csv,
        "index_header": index_header,
        "error_header": error_header,
    }


def _initial_metrics(checkpoint: CheckpointState | None) -> _DownloadMetrics:
    if checkpoint is None:
        return {
            "processed": 0,
            "downloaded_files": 0,
            "errors": 0,
            "skipped_no_video": 0,
            "completed_shortcodes": [],
        }
    return {
        "processed": checkpoint["processed"],
        "downloaded_files": checkpoint["downloaded_files"],
        "errors": checkpoint["errors"],
        "skipped_no_video": checkpoint["skipped_no_video"],
        "completed_shortcodes": list(checkpoint["completed_shortcodes"]),
    }


def _write_post_payload(
    paths: _DownloadPaths,
    shortcode: str,
    caption_text: str,
    post_comments: list[dict[str, str]],
) -> Path:
    post_dir = paths["videos_root"] / shortcode
    post_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(post_dir / "caption.txt", caption_text)
    _write_comments_snapshot(post_dir, post_comments)
    return post_dir


def _write_post_metadata(post_dir: Path, metadata: dict[str, object]) -> None:
    _atomic_write_text(
        post_dir / "metadata.json",
        json.dumps(metadata, indent=2, ensure_ascii=False),
    )


def _post_metadata(
    post: _PostTarget,
    caption_text: str,
    comment_count_reported: str | None,
    comments_saved: int,
    downloaded_for_post: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "shortcode": post.shortcode,
        "media_id": post.media_id,
        "post_url": post.post_url,
        "caption": caption_text,
        "comment_count_reported": comment_count_reported,
        "comments_saved": comments_saved,
        "video_files": downloaded_for_post,
    }


def _write_comments_snapshot(
    post_dir: Path,
    post_comments: list[dict[str, str]],
) -> None:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COMMENTS_SNAPSHOT_HEADER)
    writer.writeheader()
    for comment_row in post_comments:
        writer.writerow(comment_row)
    _atomic_write_text(post_dir / "comments.csv", buffer.getvalue())


def _build_summary(
    output_dir: Path,
    paths: _DownloadPaths,
    metrics: _DownloadMetrics,
    total_rows: int,
) -> dict[str, object]:
    return {
        "target_posts_considered": total_rows,
        "processed": metrics["processed"],
        "downloaded_files": metrics["downloaded_files"],
        "errors": metrics["errors"],
        "skipped_no_video": metrics["skipped_no_video"],
        "videos_root": str(paths["videos_root"]),
        "index_csv": str(paths["index_csv"]),
        "errors_csv": str(paths["errors_csv"]),
        "checkpoint": str(_checkpoint_file(output_dir)),
    }
