# Copyright (c) 2026
"""Unified configuration for Instagram scraper operations.

This module provides a single source of truth for configuration
dataclasses, replacing duplicate Config classes across modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """HTTP retry settings shared across Instagram API callers.

    Attributes
    ----------
    timeout : int
        Request timeout in seconds.
    max_retries : int
        Maximum number of retry attempts.
    min_delay : float
        Minimum delay between retries in seconds.
    max_delay : float
        Maximum delay between retries in seconds.
    base_retry_seconds : float
        Base for exponential backoff.

    """

    timeout: int = 30
    max_retries: int = 3
    min_delay: float = 0.05
    max_delay: float = 0.2
    base_retry_seconds: float = 1.0


@dataclass(frozen=True, slots=True)
class HttpConfig:
    """HTTP client configuration.

    Combines retry settings with authentication headers.

    Attributes
    ----------
    timeout : int
        Request timeout in seconds.
    max_retries : int
        Maximum retry attempts.
    min_delay : float
        Minimum retry delay.
    max_delay : float
        Maximum retry delay.
    cookie_header : str
        Raw Cookie header for authentication.

    """

    timeout: int = 30
    max_retries: int = 3
    min_delay: float = 0.05
    max_delay: float = 0.2
    cookie_header: str = ""

    @property
    def retry(self) -> RetryConfig:
        """Get retry configuration subset."""
        return RetryConfig(
            timeout=self.timeout,
            max_retries=self.max_retries,
            min_delay=self.min_delay,
            max_delay=self.max_delay,
        )


@dataclass(frozen=True, slots=True)
class OutputConfig:
    """Output file configuration.

    Attributes
    ----------
    output_dir : Path
        Directory for output files.
    reset_output : bool
        Clear existing output on start.
    checkpoint_every : int
        Save checkpoint every N items.

    """

    output_dir: Path = field(default_factory=lambda: Path("data"))
    reset_output: bool = False
    checkpoint_every: int = 20


@dataclass(frozen=True, slots=True)
class ScraperConfig:
    """Complete scraper configuration.

    Combines HTTP, output, and scraper-specific settings.

    Attributes
    ----------
    http : HttpConfig
        HTTP client configuration.
    output : OutputConfig
        Output file configuration.
    resume : bool
        Resume from checkpoint if available.
    limit : int | None
        Maximum items to process.

    """

    http: HttpConfig = field(default_factory=HttpConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    resume: bool = False
    limit: int | None = None


@runtime_checkable
class HasRetryConfig(Protocol):
    """Protocol for objects with retry configuration."""

    @property
    def retry(self) -> RetryConfig:
        """Retry configuration."""
        ...


@runtime_checkable
class HasOutputDir(Protocol):
    """Protocol for objects with output directory."""

    @property
    def output_dir(self) -> Path:
        """Output directory path."""
        ...
