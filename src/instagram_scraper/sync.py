# Copyright (c) 2026
"""Sync orchestration for incremental/differential scraping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from instagram_scraper.logging_utils import build_logger, configure_logging
from instagram_scraper.models import SyncSummary, TargetRecord
from instagram_scraper.providers.base import build_target_record
from instagram_scraper.storage_db import (
    create_store,
    get_sync_state,
    update_sync_state,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from structlog.typing import FilteringBoundLogger

    from instagram_scraper.storage_db import MetadataStore


PostPayload = dict[str, object]


@dataclass(frozen=True, slots=True)
class _SyncHooks:
    """Callable hooks required to execute a sync run."""

    scrape_func: Callable[..., dict[str, int]]
    get_posts_func: Callable[..., list[PostPayload]]
    filter_by_date_func: Callable[
        [list[PostPayload], datetime | None],
        list[PostPayload],
    ]
    get_latest_date_func: Callable[[list[PostPayload]], datetime | None]


@dataclass(frozen=True, slots=True)
class _SyncRequest:
    """Normalized sync request built from keyword arguments."""

    target_kind: str
    target_value: str
    output_dir: Path | None
    limit: int | None
    hooks: _SyncHooks
    provider_kwargs: dict[str, object]


@dataclass(frozen=True, slots=True)
class _SyncContext:
    """Runtime objects and state needed for a sync execution."""

    destination: Path
    store: MetadataStore
    target_key: str
    first_sync: bool
    last_post_date: datetime | None
    logger: FilteringBoundLogger


def build_sync_target_key(kind: str, value: str) -> str:
    """Build a normalized target key for sync state tracking.

    Returns
    -------
    str
        The normalized target key in the format "kind:value".

    """
    return f"{kind}:{value}"


def run_sync(mode: str, **kwargs: object) -> SyncSummary:
    """Execute an incremental sync for a target.

    Parameters
    ----------
    mode : str
        The sync mode (e.g., "profile", "hashtag").
    **kwargs : object
        Keyword arguments containing the sync target, output options, runtime
        hooks, and any provider-specific scrape arguments.

    Returns
    -------
    SyncSummary
        Summary of the sync operation with differential statistics.

    """
    request = _build_sync_request(kwargs)
    context = _create_sync_context(mode, request)
    context.logger.info(
        "sync_started",
        target_key=context.target_key,
        first_sync=context.first_sync,
        last_post_date=(
            context.last_post_date.isoformat()
            if context.last_post_date is not None
            else None
        ),
    )

    scrape_result, all_posts = _collect_sync_results(request, context.destination)
    new_posts = _filter_new_posts(request, all_posts, context.last_post_date)
    skipped_count = len(all_posts) - len(new_posts)
    latest_date = _resolve_latest_post_date(
        request,
        new_posts,
        fallback=context.last_post_date,
    )
    update_sync_state(
        context.store,
        target_key=context.target_key,
        last_post_date=latest_date,
        new_count=len(new_posts),
    )

    errors = _sync_error_count(scrape_result)
    context.logger.info(
        "sync_completed",
        target_key=context.target_key,
        new_posts=len(new_posts),
        skipped_posts=skipped_count,
        total_posts=len(all_posts),
        errors=errors,
    )

    return SyncSummary(
        run_id=f"sync-{mode}-{uuid4().hex[:8]}",
        mode=mode,
        target_key=context.target_key,
        new_posts=len(new_posts),
        skipped_posts=skipped_count,
        total_posts=len(all_posts),
        errors=errors,
        output_dir=context.destination,
        first_sync=context.first_sync,
        last_post_date=latest_date,
    )


def _build_sync_request(kwargs: dict[str, object]) -> _SyncRequest:
    runtime_keys = {
        "target_kind",
        "target_value",
        "output_dir",
        "limit",
        "scrape_func",
        "get_posts_func",
        "filter_by_date_func",
        "get_latest_date_func",
    }
    hooks = _SyncHooks(
        scrape_func=cast(
            "Callable[..., dict[str, int]]",
            _required_callable(kwargs, "scrape_func"),
        ),
        get_posts_func=cast(
            "Callable[..., list[PostPayload]]",
            _required_callable(kwargs, "get_posts_func"),
        ),
        filter_by_date_func=cast(
            "Callable[[list[PostPayload], datetime | None], list[PostPayload]]",
            _required_callable(kwargs, "filter_by_date_func"),
        ),
        get_latest_date_func=cast(
            "Callable[[list[PostPayload]], datetime | None]",
            _required_callable(kwargs, "get_latest_date_func"),
        ),
    )
    provider_kwargs = {
        key: value
        for key, value in kwargs.items()
        if key not in runtime_keys
    }
    return _SyncRequest(
        target_kind=_required_str(kwargs, "target_kind"),
        target_value=_required_str(kwargs, "target_value"),
        output_dir=_optional_path(kwargs, "output_dir"),
        limit=_optional_int(kwargs, "limit"),
        hooks=hooks,
        provider_kwargs=provider_kwargs,
    )


def _create_sync_context(mode: str, request: _SyncRequest) -> _SyncContext:
    configure_logging()
    run_id = f"sync-{mode}-{uuid4().hex[:8]}"
    logger = build_logger(run_id=run_id, mode=f"sync:{mode}")
    destination = request.output_dir or Path("data") / request.target_value
    store = create_store(destination / "state.sqlite3")
    target_key = build_sync_target_key(request.target_kind, request.target_value)
    existing_state = get_sync_state(store, target_key=target_key)
    return _SyncContext(
        destination=destination,
        store=store,
        target_key=target_key,
        first_sync=existing_state is None,
        last_post_date=(
            existing_state.last_post_date if existing_state is not None else None
        ),
        logger=logger,
    )


def _collect_sync_results(
    request: _SyncRequest,
    destination: Path,
) -> tuple[dict[str, int], list[PostPayload]]:
    scrape_kwargs = {
        "target_value": request.target_value,
        "output_dir": destination,
        "limit": request.limit,
        **request.provider_kwargs,
    }
    scrape_result = request.hooks.scrape_func(**scrape_kwargs)
    all_posts = request.hooks.get_posts_func(**scrape_kwargs)
    return scrape_result, all_posts


def _filter_new_posts(
    request: _SyncRequest,
    posts: list[PostPayload],
    last_post_date: datetime | None,
) -> list[PostPayload]:
    if last_post_date is None:
        return posts
    return request.hooks.filter_by_date_func(posts, last_post_date)


def _resolve_latest_post_date(
    request: _SyncRequest,
    posts: list[PostPayload],
    *,
    fallback: datetime | None,
) -> datetime | None:
    if not posts:
        return fallback
    return request.hooks.get_latest_date_func(posts)


def _sync_error_count(scrape_result: dict[str, int]) -> int:
    errors = scrape_result.get("errors", 0)
    return errors if isinstance(errors, int) else 0


def _required_str(kwargs: dict[str, object], key: str) -> str:
    value = kwargs.get(key)
    if isinstance(value, str):
        return value
    message = f"Expected string value for {key}"
    raise TypeError(message)


def _optional_int(kwargs: dict[str, object], key: str) -> int | None:
    value = kwargs.get(key)
    if value is None or isinstance(value, int):
        return value
    message = f"Expected integer value for {key}"
    raise TypeError(message)


def _optional_path(kwargs: dict[str, object], key: str) -> Path | None:
    value = kwargs.get(key)
    if value is None or isinstance(value, Path):
        return value
    message = f"Expected path value for {key}"
    raise TypeError(message)


def _required_callable(kwargs: dict[str, object], key: str) -> object:
    value = kwargs.get(key)
    if callable(value):
        return value
    message = f"Expected callable value for {key}"
    raise TypeError(message)


def resolve_sync_targets(
    *,
    target_kind: str,
    target_value: str,
    mode: str,
) -> list[TargetRecord]:
    """Return normalized seed targets for a sync operation.

    Returns
    -------
    list[TargetRecord]
        List containing a single target record for the sync operation.

    """
    return [
        build_target_record(
            provider="sync",
            target_kind=target_kind,
            target_value=target_value,
            mode=mode,
        ),
    ]


def filter_posts_by_date(
    posts: list[dict[str, object]],
    after_date: datetime | None,
) -> list[dict[str, object]]:
    """Filter posts to only include those after the given date.

    Returns
    -------
    list[dict[str, object]]
        Posts with date_utc later than after_date.

    """
    if after_date is None:
        return posts
    filtered: list[dict[str, object]] = []
    for post in posts:
        post_date = post.get("date_utc")
        if isinstance(post_date, datetime) and post_date > after_date:
            filtered.append(post)
        elif isinstance(post_date, str):
            try:
                parsed = datetime.fromisoformat(post_date)
                if parsed > after_date:
                    filtered.append(post)
            except (ValueError, TypeError):
                continue
    return filtered


def get_latest_post_date(posts: list[dict[str, object]]) -> datetime | None:
    """Get the latest post date from a list of posts.

    Returns
    -------
    datetime | None
        The latest post date, or None if no valid dates found.

    """
    latest: datetime | None = None
    for post in posts:
        post_date = post.get("date_utc")
        parsed: datetime | None = None
        if isinstance(post_date, datetime):
            parsed = post_date
        elif isinstance(post_date, str):
            try:
                parsed = datetime.fromisoformat(post_date)
            except (ValueError, TypeError):
                continue
        if parsed is not None and (latest is None or parsed > latest):
            latest = parsed
    return latest
