# Copyright (c) 2026
"""Download Instagram video files from previously scraped metadata."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from typing import TYPE_CHECKING, cast

from instagram_scraper.infrastructure.env import load_project_env
from instagram_scraper.infrastructure.logging import configure_logging
from instagram_scraper.workflows._video_download_cli import (
    _default_data_dir,
    _default_output_dir,
    _default_username,
    parse_args,
)
from instagram_scraper.workflows._video_download_download import (
    _download_entries,
    _index_row,
    _plan_video_downloads,
    download_video_file,
)
from instagram_scraper.workflows._video_download_io import (
    _atomic_write_text,
    _build_summary,
    _initial_metrics,
    _load_checkpoint,
    _post_metadata,
    _prepare_output,
    _save_checkpoint,
)
from instagram_scraper.workflows._video_download_media import (
    _build_session,
    _extract_video_entries,
    _fetch_media_info,
    _pick_best_video_url,
    _video_entry,
)
from instagram_scraper.workflows._video_download_process import (
    _checkpoint_state,
    _increment_metric,
    _load_resume_checkpoint,
    _mark_completed,
    _post_target_from_row,
    _process_post_row,
    _save_checkpoint_snapshot,
    _target_rows,
    _validate_post_target,
)
from instagram_scraper.workflows._video_download_types import (
    DEFAULT_DATA_DIR_FALLBACK,
    DEFAULT_USERNAME_FALLBACK,
    MEDIA_TYPE_CAROUSEL,
    MEDIA_TYPE_VIDEO,
    MIN_CHECKPOINT,
    MIN_CONCURRENT,
    MIN_DELAY_MINIMUM,
    MIN_RETRIES,
    MIN_TIMEOUT,
    Config,
    _DownloadContext,
    _DownloadPaths,
    _PostTarget,
    _VideoDownloadTask,
)
from instagram_scraper.workflows.video_download_support import (
    CommentsLookup,
    DownloadSessionPool,
    iter_target_rows,
)

if TYPE_CHECKING:
    from pathlib import Path

load_project_env()

__all__ = [
    "DEFAULT_DATA_DIR_FALLBACK",
    "DEFAULT_USERNAME_FALLBACK",
    "MEDIA_TYPE_CAROUSEL",
    "MEDIA_TYPE_VIDEO",
    "MIN_CHECKPOINT",
    "MIN_CONCURRENT",
    "MIN_DELAY_MINIMUM",
    "MIN_RETRIES",
    "MIN_TIMEOUT",
    "Config",
    "_DownloadContext",
    "_PostTarget",
    "_VideoDownloadTask",
    "_build_summary",
    "_checkpoint_state",
    "_default_data_dir",
    "_default_output_dir",
    "_default_username",
    "_download_entries",
    "_extract_video_entries",
    "_fetch_media_info",
    "_increment_metric",
    "_index_row",
    "_initial_metrics",
    "_load_checkpoint",
    "_load_comments_by_shortcode",
    "_mark_completed",
    "_maybe_checkpoint",
    "_pick_best_video_url",
    "_plan_video_downloads",
    "_post_metadata",
    "_post_target_from_row",
    "_prepare_output",
    "_save_checkpoint",
    "_target_rows",
    "_validate_post_target",
    "_video_entry",
    "_write_comments_snapshot",
    "_write_post_metadata",
    "_write_post_payload",
    "download_video_file",
    "main",
    "parse_args",
    "run",
]


def _maybe_checkpoint(context: _DownloadContext) -> None:
    if context.metrics["processed"] % context.cfg.checkpoint_every == 0:
        _save_checkpoint(
            context.cfg.output_dir,
            _checkpoint_state(context.metrics, context.completed),
        )


def _load_comments_by_shortcode(
    comments_csv: Path,
) -> dict[str, list[dict[str, str]]]:
    if not comments_csv.exists():
        return {}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with comments_csv.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            shortcode = row.get("shortcode", "")
            if shortcode:
                grouped[shortcode].append(dict(row))
    return dict(grouped)


def _write_post_payload(
    paths_or_context: _DownloadContext | dict[str, object],
    shortcode: str,
    caption_text: str,
    post_comments: list[dict[str, str]],
) -> Path:
    if isinstance(paths_or_context, _DownloadContext):
        paths = paths_or_context.paths
    else:
        paths = cast("_DownloadPaths", paths_or_context)
    post_dir = paths["videos_root"] / shortcode
    post_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(post_dir / "caption.txt", caption_text)
    _write_comments_snapshot(post_dir, post_comments)
    return post_dir


def _write_comments_snapshot(
    post_dir: Path,
    post_comments: list[dict[str, str]],
) -> None:
    header = (
        "media_id,shortcode,post_url,id,created_at_utc,text,"
        "comment_like_count,owner_username,owner_id"
    )
    lines = [header]
    keys = (
        "media_id",
        "shortcode",
        "post_url",
        "id",
        "created_at_utc",
        "text",
        "comment_like_count",
        "owner_username",
        "owner_id",
    )
    lines.extend(
        ",".join(str(row.get(key, "")) for key in keys)
        for row in post_comments
    )
    _atomic_write_text(post_dir / "comments.csv", "\n".join(lines) + "\n")


def _write_post_metadata(post_dir: Path, metadata: dict[str, object]) -> None:
    _atomic_write_text(
        post_dir / "metadata.json",
        json.dumps(metadata, indent=2, ensure_ascii=False),
    )


def run(cfg: Config) -> dict[str, object]:
    """Download video assets for the configured post export.

    Args:
        cfg: Configuration for video download.

    Returns
    -------
        Summary dictionary with download results.

    Raises
    ------
    FileNotFoundError
        If the posts CSV file is not found.
    """
    configure_logging(level="INFO")
    if not cfg.posts_csv.exists():
        message = f"posts CSV not found: {cfg.posts_csv}"
        raise FileNotFoundError(message)
    paths = _prepare_output(cfg)
    comments_by_shortcode = CommentsLookup(
        cfg.comments_csv,
        cfg.output_dir / ".video_comments.sqlite3",
    )
    checkpoint = _load_resume_checkpoint(
        cfg.output_dir, should_resume=cfg.should_resume,
    )
    metrics = _initial_metrics(checkpoint)
    completed = set(metrics["completed_shortcodes"])
    session = _build_session(cfg.cookie_header)
    download_sessions = DownloadSessionPool(cfg.cookie_header)
    context = _DownloadContext(
        cfg=cfg,
        session=session,
        paths=paths,
        comments_by_shortcode=comments_by_shortcode,
        metrics=metrics,
        completed=completed,
        download_sessions=download_sessions,
    )
    total_rows = 0
    try:
        for row in iter_target_rows(cfg.posts_csv, cfg.limit):
            total_rows += 1
            _process_post_row(context, row)
    finally:
        comments_by_shortcode.close()
        download_sessions.close()
        session.close()
    summary = _build_summary(cfg.output_dir, paths, metrics, total_rows)
    _atomic_write_text(
        cfg.output_dir / "videos_summary.json", json.dumps(summary, indent=2),
    )
    _save_checkpoint_snapshot(context, completed=True)
    return summary


def main() -> None:
    """Run the video download workflow and print a JSON summary."""
    summary = run(parse_args())
    sys.stdout.write(json.dumps(summary) + "\n")


if __name__ == "__main__":
    main()
