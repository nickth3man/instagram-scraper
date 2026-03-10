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
from instagram_scraper.core.pipeline_artifacts import (
    populate_normalized_artifacts,
    prepare_output_dir,
    record_raw_captures,
    write_targets,
)
from instagram_scraper.core.sync import resolve_sync_targets
from instagram_scraper.infrastructure.files import atomic_write_text
from instagram_scraper.infrastructure.structured_logging import (
    build_logger,
    configure_logging,
)
from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.follow_graph import FollowGraphProvider
from instagram_scraper.providers.hashtag import HashtagScrapeProvider
from instagram_scraper.providers.interactions import CommentersProvider, LikersProvider
from instagram_scraper.providers.location import LocationScrapeProvider
from instagram_scraper.providers.profile import ProfileScrapeProvider
from instagram_scraper.providers.stories import StoriesProvider
from instagram_scraper.providers.url import UrlScrapeProvider
from instagram_scraper.storage.cache import ScraperCache
from instagram_scraper.storage.database import create_store
from instagram_scraper.ui.presentation import render_run_summary


def run_pipeline(mode: str, **kwargs: object) -> int:
    """Validate, execute, and render the requested scrape mode.

    Returns
    -------
    int
        Process exit code `0` when the pipeline completes successfully.

    """
    cancellation_event = kwargs.pop("cancellation_event", None)
    progress_callback = kwargs.pop("progress_callback", None)
    execute_pipeline(
        mode,
        cancellation_event=cast("HasIsSet | None", cancellation_event),
        progress_callback=cast("Callable[[int, int], None] | None", progress_callback),
        **kwargs,
    )
    return 0


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
    direct_targets = _resolve_direct_targets(mode, kwargs)
    if direct_targets is not None:
        return direct_targets
    discovery_targets = _resolve_discovery_targets(mode, kwargs)
    if discovery_targets is not None:
        return discovery_targets
    sync_targets = _resolve_sync_mode_targets(mode, kwargs)
    if sync_targets is not None:
        return sync_targets
    message = f"Unsupported mode: {mode}"
    raise ValueError(message)


def _resolve_direct_targets(
    mode: str,
    kwargs: dict[str, object],
) -> list[TargetRecord] | None:
    if mode == "profile":
        return ProfileScrapeProvider.resolve_targets(username=str(kwargs["username"]))
    if mode == "url":
        return UrlScrapeProvider.resolve_targets(post_url=str(kwargs["post_url"]))
    if mode == "urls":
        return UrlScrapeProvider.resolve_targets(
            input_path=_path_arg(kwargs, "input_path"),
        )
    return None


def _resolve_discovery_targets(
    mode: str,
    kwargs: dict[str, object],
) -> list[TargetRecord] | None:
    resolver_map: dict[str, Callable[[], list[TargetRecord]]] = {
        "hashtag": lambda: HashtagScrapeProvider.resolve_targets(
            hashtag=str(kwargs["hashtag"]),
            limit=_optional_int(kwargs.get("limit")),
        ),
        "location": lambda: LocationScrapeProvider.resolve_targets(
            location=str(kwargs["location"]),
            limit=_optional_int(kwargs.get("limit")),
        ),
        "stories": lambda: StoriesProvider.resolve_targets(
            username=_optional_str(kwargs.get("username")),
            hashtag=_optional_str(kwargs.get("hashtag")),
            limit=_optional_int(kwargs.get("limit")),
        ),
    }
    resolver = resolver_map.get(mode)
    if resolver is not None:
        return resolver()
    if mode in {"followers", "following"}:
        return FollowGraphProvider.resolve_targets(
            mode=mode,
            username=str(kwargs["username"]),
            limit=_optional_int(kwargs.get("limit")),
        )
    interaction_provider = {
        "likers": LikersProvider,
        "commenters": CommentersProvider,
    }.get(mode)
    if interaction_provider is not None:
        return interaction_provider().resolve_targets(
            username=str(kwargs["username"]),
            posts_limit=_optional_int(kwargs.get("posts_limit")),
            limit=_optional_int(kwargs.get("limit")),
        )
    return None


def _resolve_sync_mode_targets(
    mode: str,
    kwargs: dict[str, object],
) -> list[TargetRecord] | None:
    sync_config = {
        "sync:profile": ("profile", "username"),
        "sync:hashtag": ("hashtag", "hashtag"),
        "sync:location": ("location", "location"),
    }
    target_config = sync_config.get(mode)
    if target_config is None:
        return None
    target_kind, kwarg_key = target_config
    return resolve_sync_targets(
        target_kind=target_kind,
        target_value=str(kwargs[kwarg_key]),
        mode=mode,
    )


def _run_mode(mode: str, kwargs: dict[str, object]) -> RunSummary:
    summary: RunSummary
    if mode == "profile":
        summary = ProfileScrapeProvider.run(
            username=str(kwargs["username"]),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "url":
        summary = UrlScrapeProvider.run(
            post_url=str(kwargs["post_url"]),
            output_dir=_path_arg(kwargs, "output_dir"),
            cookie_header=_optional_str(kwargs.get("cookie_header")) or "",
            request_timeout=_optional_int(kwargs.get("request_timeout")) or 30,
            max_retries=_optional_int(kwargs.get("max_retries")) or 5,
            checkpoint_every=_optional_int(kwargs.get("checkpoint_every")) or 20,
            min_delay=_optional_float(kwargs.get("min_delay")) or 0.05,
            max_delay=_optional_float(kwargs.get("max_delay")) or 0.2,
        )
    elif mode == "urls":
        summary = UrlScrapeProvider.run_urls(
            input_path=_path_arg(kwargs, "input_path"),
            output_dir=_path_arg(kwargs, "output_dir"),
            cookie_header=_optional_str(kwargs.get("cookie_header")) or "",
            resume=bool(kwargs.get("resume")),
            reset_output=bool(kwargs.get("reset_output")),
            request_timeout=_optional_int(kwargs.get("request_timeout")) or 30,
            max_retries=_optional_int(kwargs.get("max_retries")) or 5,
            checkpoint_every=_optional_int(kwargs.get("checkpoint_every")) or 20,
            min_delay=_optional_float(kwargs.get("min_delay")) or 0.05,
            max_delay=_optional_float(kwargs.get("max_delay")) or 0.2,
        )
    elif mode == "hashtag":
        summary = HashtagScrapeProvider.run(
            hashtag=str(kwargs["hashtag"]),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "location":
        summary = LocationScrapeProvider.run(
            location=str(kwargs["location"]),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode in {"followers", "following"}:
        summary = FollowGraphProvider.run(
            mode=mode,
            username=str(kwargs["username"]),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "likers":
        summary = LikersProvider().run(
            username=str(kwargs["username"]),
            posts_limit=_optional_int(kwargs.get("posts_limit")),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "commenters":
        summary = CommentersProvider().run(
            username=str(kwargs["username"]),
            posts_limit=_optional_int(kwargs.get("posts_limit")),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "stories":
        summary = StoriesProvider.run(
            username=_optional_str(kwargs.get("username")),
            hashtag=_optional_str(kwargs.get("hashtag")),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    else:
        message = f"Unsupported mode: {mode}"
        raise ValueError(message)
    return summary


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_float(value: object) -> float | None:
    return value if isinstance(value, float) else None


def _path_arg(kwargs: dict[str, object], key: str) -> Path:
    value = kwargs.get(key)
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    message = f"Expected path-like value for {key}"
    raise TypeError(message)


def _extract_output_leaf(raw_value: str, *, fallback: str) -> str:
    candidate = raw_value.rstrip("/").split("/")[-1]
    return _safe_output_name(candidate or fallback, fallback=fallback)


def _safe_output_name(raw_value: str, *, fallback: str) -> str:
    sanitized = Path(raw_value).name.strip().strip(".")
    return sanitized or fallback
