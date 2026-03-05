# Copyright (c) 2026
"""Shared provider helpers."""

from __future__ import annotations

from pathlib import Path

from instagram_scraper.models import ModeDescriptor, RunSummary


def build_run_summary(mode: str, *, output_dir: Path | None = None) -> RunSummary:
    """Construct a minimal normalized run summary for a provider.

    Returns
    -------
    RunSummary
        A normalized summary object for the requested mode.

    """
    return RunSummary(
        run_id=f"{mode}-run",
        mode=mode,
        output_dir=output_dir or Path("data") / mode,
    )


def describe_mode(
    mode: str,
    *,
    support_tier: str = "supported",
    requires_auth: bool = False,
) -> ModeDescriptor:
    """Build a mode descriptor for CLI capability reporting.

    Returns
    -------
    ModeDescriptor
        A normalized description of mode support and auth requirements.

    """
    return ModeDescriptor(
        mode=mode,
        support_tier=support_tier,
        requires_auth=requires_auth,
    )
