# Copyright (c) 2026 Nicolas Alexander
"""Download Instagram video files from previously scraped metadata."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from random import SystemRandom
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Generator

import requests

if os.name == "nt":
    import msvcrt
else:
    import fcntl

DEFAULT_DATA_DIR_FALLBACK = "data"
DEFAULT_USERNAME_FALLBACK = "target_profile"
DEFAULT_USER_AGENT = os.getenv(
    "INSTAGRAM_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
)
SUCCESS_STATUS = 200
MEDIA_TYPE_VIDEO = 2
MEDIA_TYPE_CAROUSEL = 8
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
RANDOM = SystemRandom()


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


@dataclass
class _DownloadContext:
    cfg: Config
    session: requests.Session
    paths: _DownloadPaths
    comments_by_shortcode: dict[str, list[dict[str, str]]]
    metrics: _DownloadMetrics
    completed: set[str]


@dataclass(frozen=True)
class _PostTarget:
    shortcode: str
    media_id: str
    post_url: str


@dataclass(frozen=True)
class Config:
    """Runtime configuration for video downloads."""

    output_dir: Path
    posts_csv: Path
    comments_csv: Path
    resume: bool
    reset_output: bool
    min_delay: float
    max_delay: float
    max_retries: int
    timeout: int
    checkpoint_every: int
    limit: int | None
    cookie_header: str


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
    args = parser.parse_args()
    return Config(
        output_dir=Path(args.output_dir),
        posts_csv=Path(args.posts_csv),
        comments_csv=Path(args.comments_csv),
        resume=args.resume,
        reset_output=args.reset_output,
        min_delay=max(0.0, args.min_delay),
        max_delay=max(args.min_delay, args.max_delay),
        max_retries=max(1, args.max_retries),
        timeout=max(5, args.timeout),
        checkpoint_every=max(1, args.checkpoint_every),
        limit=args.limit,
        cookie_header=args.cookie_header,
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
    if destination.exists() and destination.stat().st_size > 0:
        return True, None
    if destination.exists():
        destination.unlink()
    response, error = _request_with_retry(session, video_url, cfg, stream=True)
    if response is None:
        return False, error or "video_download_request_failed"
    temp_path = destination.with_name(
        f"{destination.name}.{os.getpid()}.{time.time_ns()}.part",
    )
    try:
        with temp_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)
            file.flush()
            os.fsync(file.fileno())
    except (OSError, requests.RequestException) as exc:
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
    if not cfg.posts_csv.exists():
        message = f"posts CSV not found: {cfg.posts_csv}"
        raise FileNotFoundError(message)
    paths = _prepare_output(cfg)
    comments_by_shortcode = _load_comments_by_shortcode(cfg.comments_csv)
    rows = _target_rows(cfg.posts_csv, cfg.limit)
    checkpoint = _load_checkpoint(cfg.output_dir) if cfg.resume else None
    metrics = _initial_metrics(checkpoint)
    completed = set(metrics["completed_shortcodes"])
    session = _build_session(cfg.cookie_header)
    context = _DownloadContext(
        cfg=cfg,
        session=session,
        paths=paths,
        comments_by_shortcode=comments_by_shortcode,
        metrics=metrics,
        completed=completed,
    )
    try:
        for row in rows:
            _process_post_row(context, row)
    finally:
        session.close()
    summary = _build_summary(cfg.output_dir, paths, metrics, len(rows))
    _atomic_write_text(
        cfg.output_dir / "videos_summary.json",
        json.dumps(summary, indent=2),
    )
    _save_checkpoint(cfg.output_dir, _checkpoint_state(metrics, completed))
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


def _cookie_value(cookie_header: str, key: str) -> str | None:
    match = re.search(r"(?:^|; )" + re.escape(key) + r"=([^;]+)", cookie_header)
    return None if match is None else match.group(1)


def _build_session(cookie_header: str) -> requests.Session:
    session = requests.Session()
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.instagram.com/",
        "Cookie": cookie_header,
    }
    app_id = os.getenv("INSTAGRAM_APP_ID")
    asbd_id = os.getenv("INSTAGRAM_ASBD_ID")
    if app_id:
        headers["X-IG-App-ID"] = app_id
    if asbd_id:
        headers["X-ASBD-ID"] = asbd_id
    csrftoken = _cookie_value(cookie_header, "csrftoken")
    session.headers.update(headers)
    if csrftoken:
        session.headers["X-CSRFToken"] = csrftoken
    return session


def _randomized_delay(cfg: Config, *, scale: float = 1.0) -> None:
    time.sleep(RANDOM.uniform(cfg.min_delay * scale, cfg.max_delay * scale))


def _request_with_retry(
    session: requests.Session,
    url: str,
    cfg: Config,
    *,
    stream: bool,
) -> tuple[requests.Response | None, str | None]:
    last_error: str | None = None
    for attempt in range(1, cfg.max_retries + 1):
        try:
            response = session.get(url, timeout=cfg.timeout, stream=stream)
        except requests.RequestException as exc:
            last_error = f"request_exception:{exc.__class__.__name__}"
            _randomized_delay(cfg, scale=2 ** (attempt - 1))
            continue
        if response.status_code == SUCCESS_STATUS:
            return response, None
        if response.status_code in RETRYABLE_STATUSES:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = (
                float(retry_after)
                if retry_after and retry_after.isdigit()
                else float(2 ** (attempt - 1))
            )
            last_error = f"http_{response.status_code}"
            _randomized_delay(cfg, scale=max(1.0, wait_seconds))
            continue
        return None, f"http_{response.status_code}"
    return None, last_error or "request_failed"


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
    best_area = -1
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
        area = width * height
        if area > best_area:
            best_area = area
            best_url = url
    return best_url


def _extract_video_entries(media_info: dict[str, object]) -> list[dict[str, object]]:
    media_type = media_info.get("media_type")
    if media_type == MEDIA_TYPE_VIDEO:
        video_url = _pick_best_video_url(media_info.get("video_versions"))
        return [] if video_url is None else [_video_entry(1, video_url)]
    if media_type != MEDIA_TYPE_CAROUSEL:
        return []
    entries: list[dict[str, object]] = []
    carousel_media = media_info.get("carousel_media")
    if not isinstance(carousel_media, list):
        return entries
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


@contextmanager
def _locked_path(path: Path) -> Generator[None]:
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if os.name == "nt":
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write("\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _atomic_write_text(path: Path, content: str) -> None:
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    with _locked_path(path):
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)


def _ensure_csv(path: Path, header: list[str], *, reset_output: bool) -> None:
    with _locked_path(path):
        if reset_output and path.exists():
            path.unlink()
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=header)
                writer.writeheader()
                file.flush()
                os.fsync(file.fileno())


def _append_csv(path: Path, header: list[str], row: dict[str, object]) -> None:
    with _locked_path(path), path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=header)
        writer.writerow(row)
        file.flush()
        os.fsync(file.fileno())


def _load_comments_by_shortcode(
    comments_csv_path: Path,
) -> dict[str, list[dict[str, str]]]:
    by_shortcode: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not comments_csv_path.exists():
        return by_shortcode
    with comments_csv_path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            shortcode = row.get("shortcode")
            if shortcode:
                by_shortcode[shortcode].append(dict(row))
    return by_shortcode


def _checkpoint_file(output_dir: Path) -> Path:
    return output_dir / "videos_checkpoint.json"


def _load_checkpoint(output_dir: Path) -> _CheckpointState | None:
    path = _checkpoint_file(output_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return cast("_CheckpointState", payload)


def _save_checkpoint(output_dir: Path, state: _CheckpointState) -> None:
    _atomic_write_text(_checkpoint_file(output_dir), json.dumps(state, indent=2))


def _prepare_output(cfg: Config) -> _DownloadPaths:
    videos_root = cfg.output_dir / "videos"
    videos_root.mkdir(parents=True, exist_ok=True)
    index_csv = cfg.output_dir / "videos_index.csv"
    errors_csv = cfg.output_dir / "videos_errors.csv"
    if cfg.reset_output:
        for path in (
            index_csv,
            errors_csv,
            _checkpoint_file(cfg.output_dir),
            cfg.output_dir / "videos_summary.json",
        ):
            if path.exists():
                path.unlink()
    index_header = [
        "shortcode",
        "media_id",
        "post_url",
        "position",
        "video_url",
        "file_path",
        "file_size_bytes",
    ]
    error_header = ["shortcode", "media_id", "post_url", "stage", "error"]
    _ensure_csv(index_csv, index_header, reset_output=cfg.reset_output)
    _ensure_csv(errors_csv, error_header, reset_output=cfg.reset_output)
    return {
        "videos_root": videos_root,
        "index_csv": index_csv,
        "errors_csv": errors_csv,
        "index_header": index_header,
        "error_header": error_header,
    }


def _target_rows(posts_csv: Path, limit: int | None) -> list[dict[str, str]]:
    with posts_csv.open("r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    filtered = [
        dict(row)
        for row in rows
        if row.get("type") in {str(MEDIA_TYPE_VIDEO), str(MEDIA_TYPE_CAROUSEL)}
    ]
    filtered.sort(
        key=lambda row: (
            0 if row.get("type") == str(MEDIA_TYPE_VIDEO) else 1,
            row.get("shortcode") or "",
        ),
    )
    return filtered if limit is None else filtered[:limit]


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
    shortcode = row.get("shortcode", "")
    media_id = row.get("media_id", "")
    post_url = row.get("post_url", "")
    post = _PostTarget(shortcode=shortcode, media_id=media_id, post_url=post_url)
    if context.cfg.resume and shortcode in context.completed:
        return
    if not shortcode or not media_id:
        _record_download_error(
            context,
            post,
            stage="input_validation",
            error="missing_shortcode_or_media_id",
        )
        _increment_metric(context.metrics, "errors")
        _increment_metric(context.metrics, "processed")
        return
    media_info, media_info_error = _fetch_media_info(
        context.session,
        media_id,
        context.cfg,
    )
    if media_info is None:
        _record_download_error(
            context,
            post,
            stage="fetch_media_info",
            error=media_info_error or "media_info_failed",
        )
        _increment_metric(context.metrics, "errors")
        _mark_completed(context.metrics, context.completed, shortcode)
        return
    video_entries = _extract_video_entries(media_info)
    if not video_entries:
        _increment_metric(context.metrics, "skipped_no_video")
        _mark_completed(context.metrics, context.completed, shortcode)
        return
    post_dir = context.paths["videos_root"] / shortcode
    post_dir.mkdir(parents=True, exist_ok=True)
    caption_text = row.get("caption", "")
    (post_dir / "caption.txt").write_text(caption_text, encoding="utf-8")
    _write_comments_snapshot(
        post_dir,
        context.comments_by_shortcode.get(shortcode, []),
    )
    downloaded_for_post = _download_entries(
        context,
        post,
        video_entries,
        post_dir=post_dir,
    )
    metadata = {
        "shortcode": shortcode,
        "media_id": media_id,
        "post_url": post_url,
        "caption": caption_text,
        "comment_count_reported": row.get("comment_count"),
        "comments_saved": len(context.comments_by_shortcode.get(shortcode, [])),
        "video_files": downloaded_for_post,
    }
    (post_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _mark_completed(context.metrics, context.completed, shortcode)
    if context.metrics["processed"] % context.cfg.checkpoint_every == 0:
        _save_checkpoint(
            context.cfg.output_dir,
            _checkpoint_state(context.metrics, context.completed),
        )
    _randomized_delay(context.cfg)


def _write_comments_snapshot(
    post_dir: Path,
    post_comments: list[dict[str, str]],
) -> None:
    comments_header = [
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
    comments_path = post_dir / "comments.csv"
    _ensure_csv(comments_path, comments_header, reset_output=False)
    if not post_comments:
        return
    with comments_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=comments_header)
        writer.writeheader()
        for comment_row in post_comments:
            writer.writerow(comment_row)


def _download_entries(
    context: _DownloadContext,
    post: _PostTarget,
    video_entries: list[dict[str, object]],
    post_dir: Path,
) -> list[dict[str, object]]:
    downloaded: list[dict[str, object]] = []
    for entry in video_entries:
        position = cast("int", entry["position"])
        video_url = cast("str", entry["video_url"])
        destination = post_dir / f"{post.shortcode}_{position:02d}.mp4"
        ok, download_error = download_video_file(
            context.session,
            video_url,
            destination,
            context.cfg,
        )
        if not ok:
            _record_download_error(
                context,
                post,
                stage="download_video_file",
                error=download_error or "video_download_failed",
            )
            _increment_metric(context.metrics, "errors")
            continue
        row = {
            "shortcode": post.shortcode,
            "media_id": post.media_id,
            "post_url": post.post_url,
            "position": position,
            "video_url": video_url,
            "file_path": str(destination),
            "file_size_bytes": destination.stat().st_size,
        }
        _append_csv(
            context.paths["index_csv"],
            context.paths["index_header"],
            row,
        )
        downloaded.append(row)
        _increment_metric(context.metrics, "downloaded_files")
    return downloaded


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
) -> _CheckpointState:
    return {
        "completed_shortcodes": sorted(completed),
        "processed": metrics["processed"],
        "downloaded_files": metrics["downloaded_files"],
        "errors": metrics["errors"],
        "skipped_no_video": metrics["skipped_no_video"],
    }


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
    try:
        payload = response.json()
    except ValueError:
        return None
    return cast("dict[str, object]", payload) if isinstance(payload, dict) else None


def _json_error(response: requests.Response, prefix: str) -> str:
    content_type = (response.headers.get("content-type") or "").lower()
    preview = (response.text or "")[:120].replace("\n", " ")
    if "json" not in content_type:
        return f"{prefix}_non_json:{content_type}:{preview}"
    return f"{prefix}_json_decode_failed"


def _increment_metric(
    metrics: _DownloadMetrics,
    key: Literal["processed", "downloaded_files", "errors", "skipped_no_video"],
) -> None:
    metrics[key] += 1


if __name__ == "__main__":
    main()
