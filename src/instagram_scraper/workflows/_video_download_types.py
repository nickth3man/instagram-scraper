# Copyright (c) 2026
"""Shared types and constants for video_downloads."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from pathlib import Path

    import requests

    from instagram_scraper.workflows.video_download_support import (
        CommentsLookup,
        DownloadSessionPool,
    )

DEFAULT_DATA_DIR_FALLBACK = "data"
DEFAULT_USERNAME_FALLBACK = "target_profile"
MEDIA_TYPE_VIDEO = 2
MEDIA_TYPE_CAROUSEL = 8
MIN_DELAY_MINIMUM = 0.0
MIN_RETRIES = 1
MIN_TIMEOUT = 5
MIN_CHECKPOINT = 1
MIN_CONCURRENT = 1
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
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


class CheckpointState(TypedDict):
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
    metrics_lock: threading.Lock = field(default_factory=threading.Lock)


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
