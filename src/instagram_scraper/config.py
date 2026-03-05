# Copyright (c) 2026
"""Configuration models for the unified scraper CLI."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AppConfig(BaseModel):
    """Top-level application configuration values."""

    model_config = ConfigDict(extra="forbid")

    output_dir: Path = Path("data")
    limit: int | None = Field(default=None, ge=1)
