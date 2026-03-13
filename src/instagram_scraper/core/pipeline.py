# Copyright (c) 2026
"""Unified provider dispatch and orchestration for scrape runs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable

from rich.console import Console

from instagram_scraper.core.capabilities import (
    describe_mode_capability,
    ensure_mode_is_runnable,
)
from instagram_scraper.core.mode_registry import (
    get_scrape_mode_definition,
    get_sync_mode_definition,
    is_registered_scrape_mode,
    is_registered_sync_mode,
)
from instagram_scraper.core.pipeline_artifacts import (
    populate_normalized_artifacts,
    prepare_output_dir,
    record_raw_captures,
    write_targets,
)
from instagram_scraper.infrastructure.files import atomic_write_text
from instagram_scraper.infrastructure.structured_logging import (
    build_logger,
    configure_logging,
)
from instagram_scraper.models import RunSummary, SyncSummary, TargetRecord
from instagram_scraper.storage.cache import ScraperCache
from instagram_scraper.storage.database import create_store
from instagram_scraper.ui.presentation import render_run_summary, render_sync_summary


def run_pipeline(mode: str, **kwargs: object) -> int:
    """Validate, execute, and render the requested scrape mode.

    Returns
    -------
    int
        Process exit code `0` when the pipeline completes successfully.

    """
    cancellation_event = kwargs.pop("cancellation_event", None)
    progress_callback = kwargs.pop("progress_callback", None)
    if is_registered_sync_mode(mode):
        execute_sync_pipeline(mode, **kwargs)
    else:
        execute_pipeline(
            mode,
            cancellation_event=cast("HasIsSet | None", cancellation_event),
            progress_callback=cast(
                "Callable[[int, int], None] | None",
                progress_callback,
            ),
            **kwargs,
        )
    return 0


def execute_sync_pipeline(mode: str, **kwargs: object) -> SyncSummary:
    """Execute an incremental sync mode and render its summary.

    Returns
    -------
    SyncSummary
        The completed incremental sync summary.

    """
    describe_mode_capability(mode)
    has_auth = bool(kwargs.get("has_auth"))
    ensure_mode_is_runnable(mode, has_auth=has_auth)
    summary = get_sync_mode_definition(mode).runner(kwargs)
    render_sync_summary(Console(), summary)
    return summary


def _check_cancellation(event: HasIsSet | None) -> None:
    if event is not None and event.is_set():
        raise PipelineCancelledError


class HasIsSet(Protocol):
    """Protocol for objects with an is_set method."""

    def is_set(self) -> bool:
        """Return whether cancellation has been requested."""
        ...


class PipelineCancelledError(Exception):
    """Raised when the pipeline is cancelled via stop event."""

    def __init__(self) -> None:
        """Initialize the cancellation error with a standard message."""
        super().__init__("Pipeline execution was cancelled")


def execute_pipeline(
    mode: str,
    *,
    cancellation_event: HasIsSet | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    **kwargs: object,
) -> RunSummary:
    """Execute a unified scrape mode and persist normalized artifacts.

    Parameters
    ----------
    mode : str
        The scrape mode to execute.
    cancellation_event : object | None
        An optional event-like object with an `is_set()` method that can
        cancel the pipeline when set.
    progress_callback : Callable[[int, int], None] | None
        Optional callback(current, total) for progress updates.
    **kwargs : object
        Additional provider-specific arguments.

    Returns
    -------
    RunSummary
        The normalized summary for the completed pipeline run.

    Raises
    ------
    TypeError
        Raised when the selected provider does not return `RunSummary`.

    """
    descriptor = describe_mode_capability(mode)
    has_auth = bool(kwargs.get("has_auth"))
    ensure_mode_is_runnable(mode, has_auth=has_auth)

    _check_cancellation(cancellation_event)
    output_dir = _resolve_output_dir(mode, kwargs)
    reset_output = bool(kwargs.get("reset_output"))
    artifact_paths = prepare_output_dir(output_dir, reset_output=reset_output)
    store = create_store(output_dir / "state.sqlite3")
    run_id = str(kwargs.get("run_id") or f"{mode}-{uuid4().hex[:8]}")
    configure_logging()
    logger = build_logger(run_id=run_id, mode=mode)
    with ScraperCache(output_dir / ".cache") as cache:
        cache.set("last_mode", mode)
        logger.info(
            "pipeline_started",
            support_tier=descriptor.support_tier,
            output_dir=str(output_dir),
        )
        targets = _resolve_targets(mode, kwargs)
        _check_cancellation(cancellation_event)
        write_targets(artifact_paths["targets"], targets, store)
        if progress_callback:
            progress_callback(10, 100)
        _check_cancellation(cancellation_event)
        summary = _run_mode(mode, {**kwargs, "output_dir": output_dir})
        if not isinstance(summary, RunSummary):
            message = f"Provider for mode {mode} did not return RunSummary"
            raise TypeError(message)
        if progress_callback:
            progress_callback(80, 100)
        _check_cancellation(cancellation_event)
        populate_normalized_artifacts(mode, output_dir, artifact_paths)
        if progress_callback:
            progress_callback(90, 100)
        if bool(kwargs.get("raw_captures")):
            record_raw_captures(mode, output_dir)
        normalized_summary = summary.model_copy(
            update={
                "run_id": run_id,
                "output_dir": output_dir,
                "targets": len(targets),
                "support_tier": descriptor.support_tier,
                "requires_auth": descriptor.requires_auth,
            },
        )
        atomic_write_text(
            artifact_paths["summary"],
            normalized_summary.model_dump_json(indent=2),
        )
        if progress_callback:
            progress_callback(100, 100)
        render_run_summary(Console(), normalized_summary)
        logger.info(
            "pipeline_completed",
            targets=normalized_summary.targets,
            users=normalized_summary.users,
            posts=normalized_summary.posts,
            comments=normalized_summary.comments,
            stories=normalized_summary.stories,
            errors=normalized_summary.errors,
        )
        return normalized_summary


def default_output_dir(mode: str) -> Path:
    """Return the default output directory for a mode.

    Returns
    -------
    Path
        The mode-specific default directory under `data/`.

    """
    return Path("data") / mode


def _resolve_output_dir(mode: str, kwargs: dict[str, object]) -> Path:
    output_dir = kwargs.get("output_dir")
    if isinstance(output_dir, Path):
        return output_dir
    if mode == "profile" and isinstance(kwargs.get("username"), str):
        return Path("data") / _safe_output_name(str(kwargs["username"]), fallback=mode)
    if mode == "url" and isinstance(kwargs.get("post_url"), str):
        shortcode = _extract_output_leaf(str(kwargs["post_url"]), fallback="url")
        return Path("data") / shortcode
    return default_output_dir(mode)


def _resolve_targets(mode: str, kwargs: dict[str, object]) -> list[TargetRecord]:
    if is_registered_scrape_mode(mode):
        return get_scrape_mode_definition(mode).target_resolver(kwargs)
    if is_registered_sync_mode(mode):
        return get_sync_mode_definition(mode).target_resolver(kwargs)
    message = f"Unsupported mode: {mode}"
    raise ValueError(message)


def _run_mode(mode: str, kwargs: dict[str, object]) -> RunSummary:
    if is_registered_scrape_mode(mode):
        return get_scrape_mode_definition(mode).runner(kwargs)
    message = f"Unsupported mode: {mode}"
    raise ValueError(message)


def _extract_output_leaf(raw_value: str, *, fallback: str) -> str:
    candidate = raw_value.rstrip("/").split("/")[-1]
    return _safe_output_name(candidate or fallback, fallback=fallback)


def _safe_output_name(raw_value: str, *, fallback: str) -> str:
    sanitized = Path(raw_value).name.strip().strip(".")
    return sanitized or fallback
