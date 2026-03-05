# Copyright (c) 2026
"""Shared provider helpers."""

from __future__ import annotations

from pathlib import Path

from instagram_scraper.capabilities import describe_mode_capability
from instagram_scraper.models import ModeDescriptor, RunSummary, TargetRecord


def build_run_summary(
    mode: str,
    *,
    output_dir: Path | None = None,
    counts: dict[str, int] | None = None,
) -> RunSummary:
    """Construct a minimal normalized run summary for a provider.

    Returns
    -------
    RunSummary
        A normalized summary object for the requested mode.

    """
    descriptor = describe_mode_capability(mode)
    normalized_counts = {
        "processed": 0,
        "posts": 0,
        "comments": 0,
        "stories": 0,
        "targets": 0,
        "users": 0,
        "errors": 0,
    }
    if counts is not None:
        normalized_counts.update(counts)
    return RunSummary(
        run_id=f"{mode}-run",
        mode=mode,
        processed=normalized_counts["processed"],
        posts=normalized_counts["posts"],
        comments=normalized_counts["comments"],
        stories=normalized_counts["stories"],
        targets=normalized_counts["targets"],
        users=normalized_counts["users"],
        errors=normalized_counts["errors"],
        output_dir=output_dir or Path("data") / mode,
        support_tier=descriptor.support_tier,
        requires_auth=descriptor.requires_auth,
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


def build_target_record(
    *,
    provider: str,
    target_kind: str,
    target_value: str,
    mode: str,
    provenance: list[str] | None = None,
) -> TargetRecord:
    """Build a normalized target payload for NDJSON or model construction.

    Returns
    -------
    TargetRecord
        Normalized target metadata for the requested mode.

    """
    descriptor = describe_mode_capability(mode)
    return TargetRecord(
        provider=provider,
        target_kind=target_kind,
        target_value=target_value,
        provenance=["cli"] if provenance is None else provenance,
        support_tier=descriptor.support_tier,
    )
