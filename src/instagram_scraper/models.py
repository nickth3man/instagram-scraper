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
    errors: int = 0
    output_dir: Path
