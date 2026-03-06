# Copyright (c) 2026
"""Configuration models for the unified scraper CLI."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AppConfig(BaseModel):
    """Top-level application configuration values."""

    model_config = ConfigDict(extra="forbid")

    output_dir: Path = Path("data")
    limit: int | None = Field(default=None, ge=1)
    raw_captures: bool = False
    request_timeout: int = Field(default=30, ge=1)
    max_retries: int = Field(default=5, ge=1)
    min_delay: float = Field(default=0.05, ge=0)
    max_delay: float = Field(default=0.2, ge=0)
    checkpoint_every: int = Field(default=20, ge=1)
