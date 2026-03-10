# Copyright (c) 2026
"""Normalized record models for scraper outputs and summaries."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class PostRecord(BaseModel):
    """Normalized post record emitted by scraper providers."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    target_kind: str
    shortcode: str
    post_url: str
    owner_username: str | None = None
    taken_at_utc: datetime | None = None


class RunSummary(BaseModel):
    """Aggregate counts for a scraper run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    mode: str
    processed: int = 0
    posts: int = 0
    comments: int = 0
    stories: int = 0
    targets: int = 0
    users: int = 0
    errors: int = 0
    output_dir: Path
    support_tier: str = "stable"
    requires_auth: bool = False


class TargetRecord(BaseModel):
    """Normalized discovery target emitted by seed providers."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    target_kind: str
    target_value: str
    provenance: list[str] = []
    support_tier: str = "stable"


class ModeDescriptor(BaseModel):
    """Describes support level and auth requirements for a scrape mode."""

    model_config = ConfigDict(extra="forbid")

    mode: str
    support_tier: str
    requires_auth: bool = False


class UserRecord(BaseModel):
    """Normalized user/account record."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    target_kind: str
    username: str
    user_id: str | None = None
    is_private: bool | None = None
    followers: int | None = None
    following: int | None = None
    posts: int | None = None


class CommentRecord(BaseModel):
    """Normalized comment record."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    target_kind: str
    comment_id: str
    post_shortcode: str
    owner_username: str | None = None
    text: str | None = None
    taken_at_utc: datetime | None = None


class StoryRecord(BaseModel):
    """Normalized story record."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    target_kind: str
    story_id: str
    owner_username: str | None = None
    media_type: str | None = None
    taken_at_utc: datetime | None = None


class ErrorRecord(BaseModel):
    """Normalized pipeline/provider error record."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    stage: str
    target: str
    error_code: str
    message: str | None = None


class RawCaptureRecord(BaseModel):
    """Reference to a raw captured payload stored on disk."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    target: str
    path: Path
    checksum: str | None = None
    source_endpoint: str | None = None


class SyncStateRecord(BaseModel):
    """Sync state for incremental scraping of a target."""

    model_config = ConfigDict(extra="forbid")

    target_key: str
    last_scraped_at: datetime | None = None
    last_post_date: datetime | None = None
    record_count: int = 0


class SyncSummary(BaseModel):
    """Summary for a sync run with differential statistics."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    mode: str
    target_key: str
    new_posts: int = 0
    skipped_posts: int = 0
    total_posts: int = 0
    errors: int = 0
    output_dir: Path
    first_sync: bool = False
    last_post_date: datetime | None = None
