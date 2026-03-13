# Copyright (c) 2026
"""Shared types for the browser_dump workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from pathlib import Path

    import requests

DEFAULT_DATA_DIR_FALLBACK = "data"
DEFAULT_USERNAME_FALLBACK = "target_profile"
POST_HEADER = [
    "media_id",
    "shortcode",
    "post_url",
    "type",
    "taken_at_utc",
    "caption",
    "like_count",
    "comment_count",
]
COMMENT_HEADER = [
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
ERROR_HEADER = ["index", "post_url", "shortcode", "media_id", "stage", "error"]
RESETTABLE_OUTPUT_NAMES = (
    "posts.ndjson",
    "comments.ndjson",
    "errors.ndjson",
    "posts.csv",
    "comments.csv",
    "errors.csv",
    "summary.json",
    "checkpoint.json",
)


class _CheckpointState(TypedDict):
    started_at_utc: str
    updated_at_utc: str
    next_index: int
    processed: int
    posts: int
    comments: int
    errors: int
    total_urls: int
    completed: NotRequired[bool]


class _PostRow(TypedDict):
    media_id: str
    shortcode: str
    post_url: str
    type: int | None
    taken_at_utc: int | None
    caption: str | None
    like_count: int | None
    comment_count: int | None


class _CommentRow(TypedDict):
    id: str
    created_at_utc: int | None
    text: str | None
    comment_like_count: int | None
    owner_username: str | None
    owner_id: str


class _ErrorRow(TypedDict):
    index: int
    post_url: str
    shortcode: str | None
    media_id: str | None
    stage: str
    error: str


class _OutputPaths(TypedDict):
    posts_ndjson: Path
    comments_ndjson: Path
    errors_ndjson: Path
    posts_csv: Path
    comments_csv: Path
    errors_csv: Path


class _RunMetrics(TypedDict):
    start_index: int
    end_index: int
    started_at_utc: str
    processed: int
    posts: int
    comments: int
    errors: int


@dataclass
class _RunContext:
    cfg: Config
    session: requests.Session
    output_paths: _OutputPaths
    headers: dict[str, list[str]]
    total_urls: int
    metrics: _RunMetrics


@dataclass(frozen=True)
class Config:
    """Runtime configuration for scraping browser-dump URLs."""

    tool_dump_path: Path
    output_dir: Path
    should_resume: bool
    should_reset_output: bool
    start_index: int
    limit: int | None
    checkpoint_every: int
    max_comment_pages: int
    min_delay: float
    max_delay: float
    request_timeout: int
    max_retries: int
    base_retry_seconds: float
    cookie_header: str


_TYPE_EXPORTS = (
    _CheckpointState,
    _PostRow,
    _CommentRow,
    _ErrorRow,
    _OutputPaths,
    _RunMetrics,
)
