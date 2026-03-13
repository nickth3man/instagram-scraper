# Copyright (c) 2026
"""Download helpers for video_downloads."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import requests

from instagram_scraper.workflows._video_download_io import _append_csv
from instagram_scraper.workflows._video_download_media import _request_with_retry
from instagram_scraper.workflows._video_download_types import (
    DOWNLOAD_CHUNK_SIZE,
    Config,
    _DownloadContext,
    _PostTarget,
    _VideoDownloadTask,
)

if TYPE_CHECKING:
    from pathlib import Path


def download_video_file(
    session: requests.Session,
    video_url: str,
    destination: Path,
    cfg: Config,
) -> tuple[bool, str | None]:
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
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
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


def _download_entries(
    context: _DownloadContext,
    post: _PostTarget,
    video_entries: list[dict[str, object]],
    post_dir: Path,
) -> list[dict[str, object]]:
    downloaded: list[dict[str, object]] = []
    tasks = _plan_video_downloads(post, video_entries, post_dir)
    with ThreadPoolExecutor(
        max_workers=context.cfg.max_concurrent_downloads,
    ) as executor:
        future_to_task = {
            executor.submit(_download_task, context, post, task): task for task in tasks
        }
        for future in as_completed(future_to_task):
            ok, result = future.result()
            if ok and isinstance(result, dict):
                downloaded.append(result)
                _append_csv(
                    context.paths["index_csv"],
                    context.paths["index_header"],
                    result,
                )
                context.metrics["downloaded_files"] += 1
            elif not ok and isinstance(result, str):
                _append_csv(
                    context.paths["errors_csv"],
                    context.paths["error_header"],
                    {
                        "shortcode": post.shortcode,
                        "media_id": post.media_id,
                        "post_url": post.post_url,
                        "stage": "download_video_file",
                        "error": result,
                    },
                )
                context.metrics["errors"] += 1
    return downloaded


def _plan_video_downloads(
    post: _PostTarget,
    video_entries: list[dict[str, object]],
    post_dir: Path,
) -> list[_VideoDownloadTask]:
    tasks: list[_VideoDownloadTask] = []
    for entry in video_entries:
        position_value = entry["position"]
        position = position_value if isinstance(position_value, int) else 0
        tasks.append(
            _VideoDownloadTask(
                position=position,
                video_url=str(entry["video_url"]),
                destination=post_dir / f"{post.shortcode}_{position:02d}.mp4",
            ),
        )
    return tasks


def _download_task(
    context: _DownloadContext,
    post: _PostTarget,
    task: _VideoDownloadTask,
) -> tuple[bool, dict[str, object] | str]:
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
        return False, download_error or "video_download_failed"
    row = _index_row(post, task)
    return True, row


def _index_row(post: _PostTarget, task: _VideoDownloadTask) -> dict[str, object]:
    return {
        "shortcode": post.shortcode,
        "media_id": post.media_id,
        "post_url": post.post_url,
        "position": task.position,
        "video_url": task.video_url,
        "file_path": str(task.destination),
        "file_size_bytes": task.destination.stat().st_size,
    }
