# Copyright (c) 2026
"""Structured logging helpers for scraper runs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger


def build_logger(*, run_id: str, mode: str) -> FilteringBoundLogger:
    """Build a structured logger pre-bound to run context.

    Returns
    -------
    FilteringBoundLogger
        A logger with `run_id` and `mode` bound into every event.

    """
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    return structlog.get_logger().bind(run_id=run_id, mode=mode)
