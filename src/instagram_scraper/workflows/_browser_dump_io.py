# Copyright (c) 2026
"""I/O helpers for browser_dump workflow."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

from instagram_scraper.infrastructure.files import (
    append_csv_row,
    atomic_write_text,
    ensure_csv_with_header,
    load_json_dict,
    write_json_line,
)
from instagram_scraper.workflows._browser_dump_types import (
    COMMENT_HEADER,
    ERROR_HEADER,
    POST_HEADER,
    RESETTABLE_OUTPUT_NAMES,
    _CheckpointState,
    _ErrorRow,
    _OutputPaths,
    _PostRow,
    _RunMetrics,
)

if TYPE_CHECKING:
    from pathlib import Path


def _iso_utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _output_headers() -> dict[str, list[str]]:
    return {
        "posts": list(POST_HEADER),
        "comments": list(COMMENT_HEADER),
        "errors": list(ERROR_HEADER),
    }


def _ensure_output_csvs(
    output_paths: _OutputPaths,
    headers: dict[str, list[str]],
    *,
    reset_output: bool,
) -> None:
    ensure_csv_with_header(
        output_paths["posts_csv"],
        headers["posts"],
        reset=reset_output,
    )
    ensure_csv_with_header(
        output_paths["comments_csv"],
        headers["comments"],
        reset=reset_output,
    )
    ensure_csv_with_header(
        output_paths["errors_csv"],
        headers["errors"],
        reset=reset_output,
    )


def _checkpoint_path(output_dir: Path) -> Path:
    return output_dir / "checkpoint.json"


def _load_checkpoint(output_dir: Path) -> _CheckpointState | None:
    path = _checkpoint_path(output_dir)
    payload = load_json_dict(path)
    return cast("_CheckpointState", payload) if payload is not None else None


def _save_checkpoint(output_dir: Path, state: _CheckpointState) -> None:
    atomic_write_text(_checkpoint_path(output_dir), json.dumps(state, indent=2))


def _prepare_output(
    output_dir: Path,
    *,
    should_reset_output: bool,
) -> _OutputPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    if should_reset_output:
        for name in RESETTABLE_OUTPUT_NAMES:
            path = output_dir / name
            if path.exists():
                path.unlink()
    return {
        "posts_ndjson": output_dir / "posts.ndjson",
        "comments_ndjson": output_dir / "comments.ndjson",
        "errors_ndjson": output_dir / "errors.ndjson",
        "posts_csv": output_dir / "posts.csv",
        "comments_csv": output_dir / "comments.csv",
        "errors_csv": output_dir / "errors.csv",
    }


def _initial_metrics(
    start_index: int,
    limit: int | None,
    urls_count: int,
    checkpoint: _CheckpointState | None,
) -> _RunMetrics:
    effective_start = start_index
    if checkpoint is not None:
        effective_start = max(effective_start, checkpoint["next_index"])
    end_index = (
        urls_count if limit is None else min(urls_count, effective_start + limit)
    )
    started_at = checkpoint["started_at_utc"] if checkpoint else _iso_utc_now()
    return {
        "start_index": effective_start,
        "end_index": end_index,
        "started_at_utc": started_at,
        "processed": checkpoint["processed"] if checkpoint else 0,
        "posts": checkpoint["posts"] if checkpoint else 0,
        "comments": checkpoint["comments"] if checkpoint else 0,
        "errors": checkpoint["errors"] if checkpoint else 0,
    }


def _checkpoint_next_index(
    output_dir: Path,
    metrics: _RunMetrics,
    total_urls: int,
    index: int,
) -> None:
    _save_checkpoint(
        output_dir,
        _checkpoint_state(metrics, total_urls, next_index=index + 1),
    )


def _record_processing_error(
    output_paths: _OutputPaths,
    error_header: list[str],
    metrics: _RunMetrics,
    error_row: _ErrorRow,
) -> None:
    _record_error(error_row, output_paths, error_header)
    _increment_metric(metrics, "errors")


def _write_post_artifact(
    output_paths: _OutputPaths,
    posts_header: list[str],
    metrics: _RunMetrics,
    post_row: _PostRow,
) -> None:
    post_payload = _post_payload(post_row)
    write_json_line(output_paths["posts_ndjson"], post_payload)
    append_csv_row(output_paths["posts_csv"], posts_header, post_payload)
    _increment_metric(metrics, "posts")


def _write_comment_artifact(
    output_paths: _OutputPaths,
    comments_header: list[str],
    metrics: _RunMetrics,
    row: dict[str, object],
) -> None:
    write_json_line(output_paths["comments_ndjson"], row)
    append_csv_row(output_paths["comments_csv"], comments_header, row)
    _increment_metric(metrics, "comments")


def _record_error(
    error_row: _ErrorRow,
    output_paths: _OutputPaths,
    error_header: list[str],
) -> None:
    error_payload = dict(error_row)
    write_json_line(output_paths["errors_ndjson"], error_payload)
    append_csv_row(output_paths["errors_csv"], error_header, error_payload)


def _checkpoint_state(
    metrics: _RunMetrics,
    total_urls: int,
    *,
    next_index: int | None = None,
    completed: bool | None = None,
) -> _CheckpointState:
    state: _CheckpointState = {
        "started_at_utc": metrics["started_at_utc"],
        "updated_at_utc": _iso_utc_now(),
        "next_index": metrics["end_index"] if next_index is None else next_index,
        "processed": metrics["processed"],
        "posts": metrics["posts"],
        "comments": metrics["comments"],
        "errors": metrics["errors"],
        "total_urls": total_urls,
    }
    if completed is not None:
        state["completed"] = completed
    return state


def _build_summary(
    output_dir: Path,
    output_paths: _OutputPaths,
    metrics: _RunMetrics,
) -> dict[str, object]:
    username = output_dir.name or "unknown"
    return {
        "target_profile": username,
        "source_url": (
            f"https://www.instagram.com/{username}/?hl=en"
            if username != "unknown"
            else None
        ),
        "started_at_utc": metrics["started_at_utc"],
        "finished_at_utc": _iso_utc_now(),
        "range": {
            "start_index": metrics["start_index"],
            "end_index_exclusive": metrics["end_index"],
        },
        "processed": metrics["processed"],
        "posts": metrics["posts"],
        "comments": metrics["comments"],
        "errors": metrics["errors"],
        "files": {
            "posts_csv": str(output_paths["posts_csv"]),
            "comments_csv": str(output_paths["comments_csv"]),
            "errors_csv": str(output_paths["errors_csv"]),
            "posts_ndjson": str(output_paths["posts_ndjson"]),
            "comments_ndjson": str(output_paths["comments_ndjson"]),
            "errors_ndjson": str(output_paths["errors_ndjson"]),
            "checkpoint": str(_checkpoint_path(output_dir)),
        },
    }


def _post_payload(post_row: _PostRow) -> dict[str, object]:
    return {
        "media_id": post_row["media_id"],
        "shortcode": post_row["shortcode"],
        "post_url": post_row["post_url"],
        "type": post_row["type"],
        "taken_at_utc": post_row["taken_at_utc"],
        "caption": post_row["caption"],
        "like_count": post_row["like_count"],
        "comment_count": post_row["comment_count"],
    }


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _increment_metric(
    metrics: _RunMetrics,
    key: Literal["processed", "posts", "comments", "errors"],
) -> None:
    metrics[key] += 1
