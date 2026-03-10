# Copyright (c) 2026
"""Processing helpers for video_downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from instagram_scraper.workflows._video_download_download import (
    _download_entries,
)
from instagram_scraper.workflows._video_download_io import (
    _append_csv,
    _load_checkpoint,
    _post_metadata,
    _save_checkpoint,
    _write_post_metadata,
    _write_post_payload,
)
from instagram_scraper.workflows._video_download_media import (
    _extract_video_entries,
    _fetch_media_info,
    _randomized_delay,
)
from instagram_scraper.workflows._video_download_types import (
    CheckpointState,
    _DownloadContext,
    _DownloadMetrics,
    _PostTarget,
)
from instagram_scraper.workflows.video_download_support import (
    CommentsLookup,
    iter_target_rows,
)


def _load_resume_checkpoint(
    output_dir: str | Path,
    *,
    should_resume: bool,
) -> CheckpointState | None:
    if not should_resume:
        return None
    return _load_checkpoint(Path(output_dir))


def _target_rows(posts_csv: Path, limit: int | None) -> list[dict[str, str]]:
    return list(iter_target_rows(posts_csv, limit))


def _process_post_row(context: _DownloadContext, row: dict[str, str]) -> None:
    post = _post_target_from_row(row)
    _log_checkpoint_progress(context)
    if _should_skip_completed_post(context, post):
        return
    if not _validate_post_target(context, post):
        return
    video_entries = _resolve_video_entries(context, post)
    if video_entries is None:
        return
    _, post_comments, post_dir = _prepare_post_bundle(context, row, post)
    downloaded_for_post = _download_entries(context, post, video_entries, post_dir)
    _write_post_bundle_metadata(post_dir, post, row, post_comments, downloaded_for_post)
    _finalize_post_processing(context, post.shortcode)


def _post_target_from_row(row: dict[str, str]) -> _PostTarget:
    return _PostTarget(
        shortcode=row.get("shortcode", ""),
        media_id=row.get("media_id", ""),
        post_url=row.get("post_url", ""),
    )


def _validate_post_target(context: _DownloadContext, post: _PostTarget) -> bool:
    if post.shortcode and post.media_id:
        return True
    _record_error_with_metric(
        context,
        post,
        stage="input_validation",
        error="missing_shortcode_or_media_id",
    )
    _increment_metric(context.metrics, "processed")
    return False


def _resolve_video_entries(
    context: _DownloadContext,
    post: _PostTarget,
) -> list[dict[str, object]] | None:
    media_info, media_info_error = _fetch_media_info(
        context.session,
        post.media_id,
        context.cfg,
    )
    if media_info is None:
        _record_error_with_metric(
            context,
            post,
            stage="fetch_media_info",
            error=media_info_error or "media_info_failed",
        )
        _mark_completed(context.metrics, context.completed, post.shortcode)
        return None
    video_entries = _extract_video_entries(media_info)
    if not video_entries:
        _increment_metric(context.metrics, "skipped_no_video")
        _mark_completed(context.metrics, context.completed, post.shortcode)
        return None
    return video_entries


def _prepare_post_bundle(
    context: _DownloadContext,
    row: dict[str, str],
    post: _PostTarget,
) -> tuple[str, list[dict[str, str]], Path]:
    caption_text = row.get("caption", "")
    post_comments = _comments_for_shortcode(
        context.comments_by_shortcode,
        post.shortcode,
    )
    post_dir = _write_post_payload(
        context.paths,
        post.shortcode,
        caption_text,
        post_comments,
    )
    return caption_text, post_comments, post_dir


def _write_post_bundle_metadata(
    post_dir: Path,
    post: _PostTarget,
    row: dict[str, str],
    post_comments: list[dict[str, str]],
    downloaded_for_post: list[dict[str, object]],
) -> None:
    _write_post_metadata(
        post_dir,
        _post_metadata(
            post,
            row.get("caption", ""),
            row.get("comment_count"),
            len(post_comments),
            downloaded_for_post,
        ),
    )


def _finalize_post_processing(context: _DownloadContext, shortcode: str) -> None:
    _mark_completed(context.metrics, context.completed, shortcode)
    _maybe_checkpoint(context)
    _randomized_delay(context.cfg)


def _record_download_error(
    context: _DownloadContext,
    post: _PostTarget,
    stage: str,
    error: str,
) -> None:
    _append_csv(
        context.paths["errors_csv"],
        context.paths["error_header"],
        {
            "shortcode": post.shortcode,
            "media_id": post.media_id,
            "post_url": post.post_url,
            "stage": stage,
            "error": error,
        },
    )


def _record_error_with_metric(
    context: _DownloadContext,
    post: _PostTarget,
    *,
    stage: str,
    error: str,
) -> None:
    _record_download_error(context, post, stage, error)
    _increment_metric(context.metrics, "errors")


def _mark_completed(
    metrics: _DownloadMetrics,
    completed: set[str],
    shortcode: str,
) -> None:
    completed.add(shortcode)
    metrics["completed_shortcodes"] = sorted(completed)
    _increment_metric(metrics, "processed")


def _checkpoint_state(
    metrics: _DownloadMetrics,
    completed: set[str],
) -> CheckpointState:
    return {
        "completed_shortcodes": sorted(completed),
        "processed": metrics["processed"],
        "downloaded_files": metrics["downloaded_files"],
        "errors": metrics["errors"],
        "skipped_no_video": metrics["skipped_no_video"],
    }


def _save_checkpoint_snapshot(
    context: _DownloadContext,
    *,
    completed: bool = False,
) -> None:
    checkpoint_state = _checkpoint_state(context.metrics, context.completed)
    if completed:
        checkpoint_state["completed"] = True
    _save_checkpoint(context.cfg.output_dir, checkpoint_state)


def _maybe_checkpoint(context: _DownloadContext) -> None:
    if context.metrics["processed"] % context.cfg.checkpoint_every == 0:
        _save_checkpoint_snapshot(context)


def _log_checkpoint_progress(context: _DownloadContext) -> None:
    if (
        context.metrics["processed"] > 0
        and context.metrics["processed"] % context.cfg.checkpoint_every == 0
    ):
        return


def _should_skip_completed_post(
    context: _DownloadContext,
    post: _PostTarget,
) -> bool:
    return context.cfg.should_resume and post.shortcode in context.completed


def _increment_metric(
    metrics: _DownloadMetrics,
    key: Literal["processed", "downloaded_files", "errors", "skipped_no_video"],
) -> None:
    metrics[key] += 1


def _comments_for_shortcode(
    comments_source: dict[str, list[dict[str, str]]] | CommentsLookup,
    shortcode: str,
) -> list[dict[str, str]]:
    if isinstance(comments_source, CommentsLookup):
        return comments_source.get(shortcode)
    return comments_source.get(shortcode, [])
