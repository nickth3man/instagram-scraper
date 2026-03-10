# Copyright (c) 2026
"""Download Instagram video files from previously scraped metadata."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

import requests

from instagram_scraper.infrastructure.env import load_project_env
from instagram_scraper.infrastructure.files import (
    append_csv_row,
    atomic_write_text,
    ensure_csv_with_header,
    load_json_dict,
)
from instagram_scraper.infrastructure.instagram_http import (
    RetryConfig,
    build_instagram_session,
    format_json_error,
    get_json_payload,
    randomized_delay,
    request_with_retry,
)
from instagram_scraper.infrastructure.logging import (
    LogContext,
    configure_logging,
    get_logger,
)
from instagram_scraper.workflows.video_download_support import (
    CommentsLookup,
    DownloadSessionPool,
    iter_target_rows,
)

load_project_env()

logger = get_logger(__name__)

DEFAULT_DATA_DIR_FALLBACK = "data"
DEFAULT_USERNAME_FALLBACK = "target_profile"
MEDIA_TYPE_VIDEO = 2
MEDIA_TYPE_CAROUSEL = 8

# Validation thresholds for CLI arguments
MIN_DELAY_MINIMUM = 0.0
MIN_RETRIES = 1
MIN_TIMEOUT = 5
MIN_CHECKPOINT = 1
MIN_CONCURRENT = 1

# Download configuration
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
DEFAULT_BASE_RETRY_SECONDS = 1.0
INITIAL_BEST_AREA = -1
COMMENTS_SNAPSHOT_HEADER = [
    "media_id",
    "shortcode",
    "post_url",
    "id",
    "created_at_utc",
    "text",
    "comment_like_count",
    "owner_username",
    "owner_id",
]
VIDEO_INDEX_HEADER = [
    "shortcode",
    "media_id",
    "post_url",
    "position",
    "video_url",
    "file_path",
    "file_size_bytes",
]
DOWNLOAD_ERROR_HEADER = ["shortcode", "media_id", "post_url", "stage", "error"]
RESETTABLE_OUTPUT_FILENAMES = (
    "videos_index.csv",
    "videos_errors.csv",
    "videos_checkpoint.json",
    "videos_summary.json",
)


class _CheckpointState(TypedDict):
    completed_shortcodes: list[str]
    processed: int
    downloaded_files: int
    errors: int
    skipped_no_video: int
    completed: NotRequired[bool]


class _DownloadPaths(TypedDict):
    videos_root: Path
    index_csv: Path
    errors_csv: Path
    index_header: list[str]
    error_header: list[str]


class _DownloadMetrics(TypedDict):
    processed: int
    downloaded_files: int
    errors: int
    skipped_no_video: int
    completed_shortcodes: list[str]


@dataclass(slots=True)
class _DownloadContext:
    cfg: Config
    session: requests.Session
    paths: _DownloadPaths
    comments_by_shortcode: dict[str, list[dict[str, str]]] | CommentsLookup
    metrics: _DownloadMetrics
    completed: set[str]
    download_sessions: DownloadSessionPool | None = None


@dataclass(frozen=True, slots=True)
class _PostTarget:
    shortcode: str
    media_id: str
    post_url: str


@dataclass(frozen=True, slots=True)
class _VideoDownloadTask:
    position: int
    video_url: str
    destination: Path


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration for video downloads."""

    output_dir: Path
    posts_csv: Path
    comments_csv: Path
    should_resume: bool
    should_reset_output: bool
    min_delay: float
    max_delay: float
    max_retries: int
    timeout: int
    checkpoint_every: int
    limit: int | None
    cookie_header: str
    max_concurrent_downloads: int


def parse_args() -> Config:
    """Parse CLI arguments into a validated download configuration.

    Returns
    -------
    Config
        The normalized runtime configuration for the downloader.

    """
    parser = argparse.ArgumentParser()
    defaults_output_dir = _default_output_dir()
    parser.add_argument("--output-dir", default=str(defaults_output_dir))
    parser.add_argument("--posts-csv", default=str(defaults_output_dir / "posts.csv"))
    parser.add_argument(
        "--comments-csv",
        default=str(defaults_output_dir / "comments.csv"),
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    parser.add_argument("--min-delay", type=float, default=0.05)
    parser.add_argument("--max-delay", type=float, default=0.2)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cookie-header", default=os.getenv("IG_COOKIE_HEADER", ""))
    parser.add_argument("--max-concurrent-downloads", type=int, default=3)
    args = parser.parse_args()
    return Config(
        output_dir=Path(args.output_dir),
        posts_csv=Path(args.posts_csv),
        comments_csv=Path(args.comments_csv),
        should_resume=args.resume,
        should_reset_output=args.reset_output,
        min_delay=max(MIN_DELAY_MINIMUM, args.min_delay),
        max_delay=max(args.min_delay, args.max_delay),
        max_retries=max(MIN_RETRIES, args.max_retries),
        timeout=max(MIN_TIMEOUT, args.timeout),
        checkpoint_every=max(MIN_CHECKPOINT, args.checkpoint_every),
        limit=args.limit,
        cookie_header=args.cookie_header,
        max_concurrent_downloads=max(MIN_CONCURRENT, args.max_concurrent_downloads),
    )


def download_video_file(
    session: requests.Session,
    video_url: str,
    destination: Path,
    cfg: Config,
) -> tuple[bool, str | None]:
    """Download a video asset atomically, cleaning partial files on failure.

    Returns
    -------
    tuple[bool, str | None]
        Whether the download succeeded and any resulting error code.

    """
    # Reuse an existing finished file instead of downloading the same bytes again.
    if destination.exists() and destination.stat().st_size > 0:
        logger.debug(
            "video_file_exists_skipping",
            extra={"destination": str(destination)},
        )
        return True, None
    if destination.exists():
        destination.unlink()

    logger.info(
        "downloading_video_file",
        extra={"url": video_url, "destination": str(destination)},
    )
    response, error = _request_with_retry(session, video_url, cfg, stream=True)
    if response is None:
        return False, error or "video_download_request_failed"
    # Download into a temporary ".part" file first so interrupted runs never
    # leave behind a file that looks complete but is actually truncated.
    temp_path = destination.with_name(
        f"{destination.name}.{os.getpid()}.{time.time_ns()}.part",
    )
    try:
        with temp_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if chunk:
                    file.write(chunk)
            file.flush()
            os.fsync(file.fileno())
    except (OSError, requests.RequestException) as exc:
        logger.exception(
            "video_download_write_error",
            extra={"error": str(exc), "temp_path": str(temp_path)},
        )
        temp_path.unlink(missing_ok=True)
        return False, f"file_write_error:{exc.__class__.__name__}"
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    if not temp_path.exists() or temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        return False, "video_file_empty"
    try:
        temp_path.replace(destination)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        return False, f"file_write_error:{exc.__class__.__name__}"
    return True, None


def run(cfg: Config) -> dict[str, object]:
    """Download all videos referenced in `posts.csv` and persist summary artifacts.

    Returns
    -------
    dict[str, object]
        Summary metadata for the completed download run.

    Raises
    ------
    FileNotFoundError
        Raised when the configured `posts.csv` file does not exist.

    """
    # Initialize structured logging for the run
    configure_logging(level="INFO")
    logger.info(
        "download_run_started",
        extra={
            "output_dir": str(cfg.output_dir),
            "posts_csv": str(cfg.posts_csv),
            "should_resume": cfg.should_resume,
            "should_reset_output": cfg.should_reset_output,
            "limit": cfg.limit,
            "max_concurrent_downloads": cfg.max_concurrent_downloads,
        },
    )
    if not cfg.posts_csv.exists():
        message = f"posts CSV not found: {cfg.posts_csv}"
        logger.error("posts_csv_not_found", extra={"posts_csv": str(cfg.posts_csv)})
        raise FileNotFoundError(message)

    logger.info(
        "starting_video_downloads",
        extra={
            "output_dir": str(cfg.output_dir),
            "posts_csv": str(cfg.posts_csv),
            "should_resume": cfg.should_resume,
            "should_reset_output": cfg.should_reset_output,
            "limit": cfg.limit,
            "max_concurrent_downloads": cfg.max_concurrent_downloads,
        },
    )
    paths = _prepare_output(cfg)
    comments_by_shortcode = CommentsLookup(
        cfg.comments_csv,
        cfg.output_dir / ".video_comments.sqlite3",
    )
    checkpoint = _load_resume_checkpoint(
        cfg.output_dir,
        should_resume=cfg.should_resume,
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
        cfg.output_dir / "videos_summary.json",
        json.dumps(summary, indent=2),
    )
    _save_checkpoint_snapshot(context, completed=True)
    return summary


def main() -> None:
    """Run the downloader and emit the final summary as JSON."""
    summary = run(parse_args())
    sys.stdout.write(json.dumps(summary) + "\n")


def _default_data_dir() -> Path:
    return Path(os.getenv("INSTAGRAM_DATA_DIR", DEFAULT_DATA_DIR_FALLBACK))


def _default_username() -> str:
    return os.getenv("INSTAGRAM_USERNAME", DEFAULT_USERNAME_FALLBACK)


def _default_output_dir() -> Path:
    return _default_data_dir() / _default_username()


def _build_session(cookie_header: str) -> requests.Session:
    return build_instagram_session(cookie_header)


def _randomized_delay(cfg: Config, *, scale: float = 1.0) -> None:
    randomized_delay(cfg.min_delay, cfg.max_delay, scale=scale)


def _request_with_retry(
    session: requests.Session,
    url: str,
    cfg: Config,
    *,
    stream: bool,
) -> tuple[requests.Response | None, str | None]:
    return request_with_retry(
        session,
        url,
        RetryConfig(
            timeout=cfg.timeout,
            max_retries=cfg.max_retries,
            min_delay=cfg.min_delay,
            max_delay=cfg.max_delay,
            base_retry_seconds=DEFAULT_BASE_RETRY_SECONDS,
        ),
        stream=stream,
    )


def _fetch_media_info(
    session: requests.Session,
    media_id: str,
    cfg: Config,
) -> tuple[dict[str, object] | None, str | None]:
    response, error = _request_with_retry(
        session,
        f"https://www.instagram.com/api/v1/media/{media_id}/info/",
        cfg,
        stream=False,
    )
    if response is None:
        return None, error or "media_info_request_failed"
    payload = _json_payload(response)
    if payload is None:
        return None, _json_error(response, "media_info")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None, "media_info_empty"
    first = items[0]
    if not isinstance(first, dict):
        return None, "media_info_invalid"
    return cast("dict[str, object]", first), None


def _pick_best_video_url(video_versions: object) -> str | None:
    if not isinstance(video_versions, list):
        return None
    best_url: str | None = None
    best_area = INITIAL_BEST_AREA
    for version in video_versions:
        if not isinstance(version, dict):
            continue
        version_dict = cast("dict[str, object]", version)
        width = version_dict.get("width")
        height = version_dict.get("height")
        url = version_dict.get("url")
        if (
            not isinstance(width, int)
            or not isinstance(height, int)
            or not isinstance(url, str)
        ):
            continue
        # Use the largest resolution available so saved files are the highest quality.
        area = width * height
        if area > best_area:
            best_area = area
            best_url = url
    return best_url


def _extract_video_entries(media_info: dict[str, object]) -> list[dict[str, object]]:
    media_type = media_info.get("media_type")
    if media_type == MEDIA_TYPE_VIDEO:
        # A normal video post has one downloadable video file.
        video_url = _pick_best_video_url(media_info.get("video_versions"))
        return [] if video_url is None else [_video_entry(1, video_url)]
    if media_type != MEDIA_TYPE_CAROUSEL:
        return []
    entries: list[dict[str, object]] = []
    carousel_media = media_info.get("carousel_media")
    if not isinstance(carousel_media, list):
        return entries
    # Carousel posts can mix images and videos, so inspect each child separately.
    for index, child in enumerate(carousel_media, start=1):
        if not isinstance(child, dict):
            continue
        child_dict = cast("dict[str, object]", child)
        if child_dict.get("media_type") != MEDIA_TYPE_VIDEO:
            continue
        video_url = _pick_best_video_url(child_dict.get("video_versions"))
        if video_url is not None:
            entries.append(_video_entry(index, video_url))
    return entries


def _video_entry(position: int, video_url: str) -> dict[str, object]:
    return {
        "position": position,
        "media_type": MEDIA_TYPE_VIDEO,
        "video_url": video_url,
    }


def _atomic_write_text(path: Path, content: str) -> None:
    atomic_write_text(path, content)


def _ensure_csv(path: Path, header: list[str], *, reset_output: bool) -> None:
    ensure_csv_with_header(path, header, reset=reset_output)


def _append_csv(path: Path, header: list[str], row: dict[str, object]) -> None:
    append_csv_row(path, header, row)


def _load_comments_by_shortcode(
    comments_csv_path: Path,
) -> dict[str, list[dict[str, str]]]:
    by_shortcode: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not comments_csv_path.exists():
        return by_shortcode
    with comments_csv_path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if shortcode := row.get("shortcode"):
                # This turns one big CSV into a lookup table: shortcode -> comments.
                by_shortcode[shortcode].append(dict(row))
    return by_shortcode


def _checkpoint_file(output_dir: Path) -> Path:
    return output_dir / "videos_checkpoint.json"


def _load_checkpoint(output_dir: Path) -> _CheckpointState | None:
    path = _checkpoint_file(output_dir)
    payload = load_json_dict(path)
    return cast("_CheckpointState", payload) if payload is not None else None


def _load_resume_checkpoint(
    output_dir: Path,
    *,
    should_resume: bool,
) -> _CheckpointState | None:
    if not should_resume:
        logger.info("resume_disabled", extra={"output_dir": str(output_dir)})
        return None
    checkpoint = _load_checkpoint(output_dir)
    if checkpoint is None:
        logger.info("resume_checkpoint_missing", extra={"output_dir": str(output_dir)})
        return None
    logger.info(
        "resume_checkpoint_loaded",
        extra={
            "output_dir": str(output_dir),
            "processed": checkpoint["processed"],
            "downloaded_files": checkpoint["downloaded_files"],
            "errors": checkpoint["errors"],
        },
    )
    return checkpoint


def _save_checkpoint(output_dir: Path, state: _CheckpointState) -> None:
    logger.info(
        "checkpoint_saved",
        extra={
            "output_dir": str(output_dir),
            "processed": state["processed"],
            "downloaded_files": state["downloaded_files"],
            "errors": state["errors"],
            "completed": state.get("completed", False),
        },
    )
    _atomic_write_text(_checkpoint_file(output_dir), json.dumps(state, indent=2))


def _prepare_output(cfg: Config) -> _DownloadPaths:
    videos_root = cfg.output_dir / "videos"
    videos_root.mkdir(parents=True, exist_ok=True)
    index_csv = cfg.output_dir / "videos_index.csv"
    errors_csv = cfg.output_dir / "videos_errors.csv"
    if cfg.should_reset_output:
        # Reset mode removes old bookkeeping files and keeps the directory layout
        # simple for the next run.
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


def _target_rows(posts_csv: Path, limit: int | None) -> list[dict[str, str]]:
    return list(iter_target_rows(posts_csv, limit))


def _initial_metrics(checkpoint: _CheckpointState | None) -> _DownloadMetrics:
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


def _process_post_row(context: _DownloadContext, row: dict[str, str]) -> None:
    post = _post_target_from_row(row)
    with LogContext(shortcode=post.shortcode, media_id=post.media_id):
        _log_checkpoint_progress(context)
        if _should_skip_completed_post(context, post):
            # Resume mode skips posts already marked complete in checkpoint.
            return
        if not _validate_post_target(context, post):
            return

        # Request-scoped processing log
        logger.info("processing post")

        video_entries = _resolve_video_entries(context, post)
        if video_entries is None:
            return
        _, post_comments, post_dir = _prepare_post_bundle(
            context,
            row,
            post,
        )
        downloaded_for_post = _download_entries(
            context,
            post,
            video_entries,
            post_dir=post_dir,
        )
        _write_post_bundle_metadata(
            post_dir,
            post,
            row,
            post_comments,
            downloaded_for_post,
        )
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


def _write_post_payload(
    context: _DownloadContext,
    shortcode: str,
    caption_text: str,
    post_comments: list[dict[str, str]],
) -> Path:
    post_dir = context.paths["videos_root"] / shortcode
    post_dir.mkdir(parents=True, exist_ok=True)
    # Save the caption and comments next to the videos so each post directory is a
    # self-contained bundle of everything we know about that post.
    _atomic_write_text(post_dir / "caption.txt", caption_text)
    _write_comments_snapshot(post_dir, post_comments)
    return post_dir


def _write_post_metadata(
    post_dir: Path,
    metadata: dict[str, object],
) -> None:
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
    comments_path = post_dir / "comments.csv"
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COMMENTS_SNAPSHOT_HEADER)
    writer.writeheader()
    for comment_row in post_comments:
        writer.writerow(comment_row)
    _atomic_write_text(comments_path, buffer.getvalue())


def _log_checkpoint_progress(context: _DownloadContext) -> None:
    if (
        context.metrics["processed"] > 0
        and context.metrics["processed"] % context.cfg.checkpoint_every == 0
    ):
        logger.info(
            "checkpoint_progress",
            extra={
                "processed": context.metrics["processed"],
                "completed_shortcodes": len(context.completed),
            },
        )


def _should_skip_completed_post(
    context: _DownloadContext,
    post: _PostTarget,
) -> bool:
    return context.cfg.should_resume and post.shortcode in context.completed


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
        context,
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


def _finalize_post_processing(
    context: _DownloadContext,
    shortcode: str,
) -> None:
    _mark_completed(context.metrics, context.completed, shortcode)
    _maybe_checkpoint(context)
    _randomized_delay(context.cfg)


def _download_entries(
    context: _DownloadContext,
    post: _PostTarget,
    video_entries: list[dict[str, object]],
    post_dir: Path,
) -> list[dict[str, object]]:
    downloaded: list[dict[str, object]] = []
    tasks = _plan_video_downloads(post, video_entries, post_dir)

    max_workers = context.cfg.max_concurrent_downloads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(_download_task, context, post, task): task for task in tasks
        }

        for future in as_completed(future_to_task):
            row = future.result()
            if row is not None:
                downloaded.append(row)

    return downloaded


def _plan_video_downloads(
    post: _PostTarget,
    video_entries: list[dict[str, object]],
    post_dir: Path,
) -> list[_VideoDownloadTask]:
    tasks: list[_VideoDownloadTask] = []
    for entry in video_entries:
        position = cast("int", entry["position"])
        video_url = cast("str", entry["video_url"])
        tasks.append(
            _VideoDownloadTask(
                position=position,
                video_url=video_url,
                destination=post_dir / f"{post.shortcode}_{position:02d}.mp4",
            ),
        )
    return tasks


def _download_task(
    context: _DownloadContext,
    post: _PostTarget,
    task: _VideoDownloadTask,
) -> dict[str, object] | None:
    session = (
        context.download_sessions.get()
        if context.download_sessions is not None
        else context.session
    )
    ok, download_error = download_video_file(
        session,
        task.video_url,
        task.destination,
        context.cfg,
    )
    if not ok:
        _record_error_with_metric(
            context,
            post,
            stage="download_video_file",
            error=download_error or "video_download_failed",
        )
        return None
    row = _index_row(post, task)
    _append_csv(
        context.paths["index_csv"],
        context.paths["index_header"],
        row,
    )
    _increment_metric(context.metrics, "downloaded_files")
    return row


def _index_row(post: _PostTarget, task: _VideoDownloadTask) -> dict[str, object]:
    # The index CSV is the master list of every saved file and where it lives.
    return {
        "shortcode": post.shortcode,
        "media_id": post.media_id,
        "post_url": post.post_url,
        "position": task.position,
        "video_url": task.video_url,
        "file_path": str(task.destination),
        "file_size_bytes": task.destination.stat().st_size,
    }


def _record_download_error(
    context: _DownloadContext,
    post: _PostTarget,
    stage: str,
    error: str,
) -> None:
    logger.warning(
        "post_download_error",
        extra={
            "shortcode": post.shortcode,
            "media_id": post.media_id,
            "stage": stage,
            "error": error,
        },
    )
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
    # Keep the set for fast membership checks, then save a sorted list so output
    # files stay stable between runs.
    completed.add(shortcode)
    metrics["completed_shortcodes"] = sorted(completed)
    _increment_metric(metrics, "processed")


def _checkpoint_state(
    metrics: _DownloadMetrics,
    completed: set[str],
) -> _CheckpointState:
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
    _save_checkpoint(
        context.cfg.output_dir,
        checkpoint_state,
    )


def _maybe_checkpoint(context: _DownloadContext) -> None:
    if context.metrics["processed"] % context.cfg.checkpoint_every == 0:
        # Save progress regularly so long download runs can resume after interruption.
        logger.info(
            "saving_checkpoint",
            extra={
                "processed": context.metrics["processed"],
                "downloaded_files": context.metrics["downloaded_files"],
                "errors": context.metrics["errors"],
            },
        )
        _save_checkpoint_snapshot(context)


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


def _json_payload(response: requests.Response) -> dict[str, object] | None:
    return get_json_payload(response)


def _json_error(response: requests.Response, prefix: str) -> str:
    return format_json_error(response, prefix)


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


if __name__ == "__main__":
    main()
