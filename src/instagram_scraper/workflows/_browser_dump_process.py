# Copyright (c) 2026
"""Processing helpers for the browser_dump workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from instagram_scraper.workflows._browser_dump_fetch import (
    _extract_shortcode,
    _fetch_comments,
    _fetch_media_info,
    _randomized_delay,
    fetch_media_id,
)
from instagram_scraper.workflows._browser_dump_io import (
    _checkpoint_next_index,
    _increment_metric,
    _optional_int,
    _optional_str,
    _record_processing_error,
    _write_comment_artifact,
    _write_post_artifact,
)

if TYPE_CHECKING:
    from instagram_scraper.workflows._browser_dump_types import (
        _PostRow,
        _RunContext,
    )


def _process_url(context: _RunContext, index: int, post_url: str) -> None:
    shortcode = _extract_shortcode(post_url)
    if shortcode is None:
        _record_processing_error(
            context.output_paths,
            context.headers["errors"],
            context.metrics,
            {
                "index": index,
                "post_url": post_url,
                "shortcode": None,
                "media_id": None,
                "stage": "extract_shortcode",
                "error": "missing_shortcode",
            },
        )
        _increment_metric(context.metrics, "processed")
        _checkpoint_next_index(
            context.cfg.output_dir,
            context.metrics,
            context.total_urls,
            index,
        )
        return
    media_id, media_id_error = fetch_media_id(
        context.session,
        post_url,
        shortcode,
        context.cfg,
    )
    if media_id is None:
        _record_processing_error(
            context.output_paths,
            context.headers["errors"],
            context.metrics,
            {
                "index": index,
                "post_url": post_url,
                "shortcode": shortcode,
                "media_id": None,
                "stage": "fetch_media_id",
                "error": media_id_error or "media_id_not_found",
            },
        )
        _increment_metric(context.metrics, "processed")
        _checkpoint_next_index(
            context.cfg.output_dir,
            context.metrics,
            context.total_urls,
            index,
        )
        _randomized_delay(
            context.cfg.min_delay,
            context.cfg.max_delay,
        )
        return
    _process_media(context, index, post_url, shortcode, media_id)
    _increment_metric(context.metrics, "processed")
    if context.metrics["processed"] % context.cfg.checkpoint_every == 0:
        _checkpoint_next_index(
            context.cfg.output_dir,
            context.metrics,
            context.total_urls,
            index,
        )
    _randomized_delay(context.cfg.min_delay, context.cfg.max_delay)


def _process_media(
    context: _RunContext,
    index: int,
    post_url: str,
    shortcode: str,
    media_id: str,
) -> None:
    media_info, media_info_error = _fetch_media_info(
        context.session,
        media_id,
        context.cfg,
    )
    if media_info is None:
        _record_processing_error(
            context.output_paths,
            context.headers["errors"],
            context.metrics,
            {
                "index": index,
                "post_url": post_url,
                "shortcode": shortcode,
                "media_id": media_id,
                "stage": "fetch_media_info",
                "error": media_info_error or "media_info_failed",
            },
        )
        _checkpoint_next_index(
            context.cfg.output_dir,
            context.metrics,
            context.total_urls,
            index,
        )
        _randomized_delay(context.cfg.min_delay, context.cfg.max_delay)
        return
    post_row = _post_row(media_id, shortcode, post_url, media_info)
    _write_post_artifact(
        context.output_paths,
        context.headers["posts"],
        context.metrics,
        post_row,
    )
    comments_error = _write_comments(context, media_id, shortcode, post_url, post_row)
    if comments_error is not None:
        _record_processing_error(
            context.output_paths,
            context.headers["errors"],
            context.metrics,
            {
                "index": index,
                "post_url": post_url,
                "shortcode": shortcode,
                "media_id": media_id,
                "stage": "fetch_comments",
                "error": comments_error,
            },
        )


def _write_comments(
    context: _RunContext,
    media_id: str,
    shortcode: str,
    post_url: str,
    post_row: _PostRow,
) -> str | None:
    declared_comment_count = post_row["comment_count"]
    if declared_comment_count is None or declared_comment_count <= 0:
        return None
    post_comments, comments_error = _fetch_comments(
        context.session,
        media_id,
        context.cfg,
    )
    for comment in post_comments:
        _write_comment_artifact(
            context.output_paths,
            context.headers["comments"],
            context.metrics,
            {
                "media_id": media_id,
                "shortcode": shortcode,
                "post_url": post_url,
                **comment,
            },
        )
    return comments_error


def _post_row(
    media_id: str,
    shortcode: str,
    post_url: str,
    media_info: dict[str, object],
) -> _PostRow:
    caption = media_info.get("caption")
    caption_text: str | None = None
    if isinstance(caption, dict):
        caption_text = _optional_str(cast("dict[str, object]", caption).get("text"))
    return {
        "media_id": media_id,
        "shortcode": shortcode,
        "post_url": post_url,
        "type": _optional_int(media_info.get("media_type")),
        "taken_at_utc": _optional_int(media_info.get("taken_at_utc")),
        "caption": caption_text,
        "like_count": _optional_int(media_info.get("like_count")),
        "comment_count": _optional_int(media_info.get("comment_count")),
    }
