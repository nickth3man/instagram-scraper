# Copyright (c) 2026
"""Configuration models for the unified scraper CLI."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    @model_validator(mode="after")
    def validate_delay_bounds(self) -> "AppConfig":
        """Ensure delay bounds are ordered.

        Returns
        -------
        AppConfig
            The validated config instance.

        Raises
        ------
        ValueError
            Raised when `min_delay` exceeds `max_delay`.

        """
        if self.min_delay > self.max_delay:
            message = "min_delay must be less than or equal to max_delay"
            raise ValueError(message)
        return self
