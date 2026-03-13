# Copyright (c) 2026
"""Sync-mode helper implementations."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from instagram_scraper.core.mode_helpers import (
    _load_attr,
    _load_sync_attr,
    _ModeKwargs,
    _optional_int,
    _optional_path,
    _required_str,
)

if TYPE_CHECKING:
    from pathlib import Path

    from instagram_scraper.models import SyncSummary, TargetRecord


def _sync_targets(
    *,
    mode: str,
    target_kind: str,
    target_key: str,
    kwargs: _ModeKwargs,
) -> list[TargetRecord]:
    resolver = cast("Any", _load_sync_attr("resolve_sync_targets"))
    return resolver(
        target_kind=target_kind,
        target_value=_required_str(kwargs, target_key),
        mode=mode,
    )


def _profile_sync_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    return _sync_targets(
        mode="sync:profile",
        target_kind="profile",
        target_key="username",
        kwargs=kwargs,
    )


def _hashtag_sync_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    return _sync_targets(
        mode="sync:hashtag",
        target_kind="hashtag",
        target_key="hashtag",
        kwargs=kwargs,
    )


def _location_sync_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    return _sync_targets(
        mode="sync:location",
        target_kind="location",
        target_key="location",
        kwargs=kwargs,
    )


def _load_profile_sync_posts(
    *,
    output_dir: Path,
    **_: object,
) -> list[dict[str, object]]:
    dataset_path = output_dir / "instagram_dataset.json"
    if not dataset_path.exists():
        return []
    with dataset_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return []
    posts = payload.get("posts")
    return list(posts) if isinstance(posts, list) else []


def _profile_sync_scrape(
    *,
    target_value: str,
    output_dir: Path,
    **_: object,
) -> SyncSummary:
    runner = cast(
        "Any",
        _load_attr("instagram_scraper.workflows.profile", "run_profile_scrape"),
    )
    return cast("SyncSummary", runner(username=target_value, output_dir=output_dir))


def _synthetic_sync_posts(target_value: str, count: int) -> list[dict[str, object]]:
    now = datetime.now(UTC)
    return [
        {
            "shortcode": f"{target_value}-{index}",
            "taken_at_utc": (now - timedelta(hours=index)).isoformat(),
        }
        for index in range(count)
    ]


def _discovery_target_count(
    module_name: str,
    provider_attr: str,
    target_key: str,
    target_value: str,
    limit: int | None,
) -> int:
    provider_class = cast("Any", _load_attr(module_name, provider_attr))
    provider = provider_class()
    records = provider.resolve_targets(**{target_key: target_value, "limit": limit})
    discovered = len(records) if isinstance(records, list) else 0
    return discovered if limit is None else min(discovered, limit)


def _hashtag_sync_scrape(
    *,
    target_value: str,
    output_dir: Path | None,
    limit: int | None,
    **_: object,
) -> SyncSummary:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.hashtag", "HashtagScrapeProvider"),
    )()
    return cast(
        "SyncSummary",
        provider.run(hashtag=target_value, output_dir=output_dir, limit=limit),
    )


def _location_sync_scrape(
    *,
    target_value: str,
    output_dir: Path | None,
    limit: int | None,
    **_: object,
) -> SyncSummary:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.location", "LocationScrapeProvider"),
    )()
    return cast(
        "SyncSummary",
        provider.run(location=target_value, output_dir=output_dir, limit=limit),
    )


def _hashtag_sync_posts(
    *,
    target_value: str,
    limit: int | None,
    **_: object,
) -> list[dict[str, object]]:
    return _synthetic_sync_posts(
        target_value,
        _discovery_target_count(
            "instagram_scraper.providers.hashtag",
            "HashtagScrapeProvider",
            "hashtag",
            target_value,
            limit,
        ),
    )


def _location_sync_posts(
    *,
    target_value: str,
    limit: int | None,
    **_: object,
) -> list[dict[str, object]]:
    return _synthetic_sync_posts(
        target_value,
        _discovery_target_count(
            "instagram_scraper.providers.location",
            "LocationScrapeProvider",
            "location",
            target_value,
            limit,
        ),
    )


def _profile_sync_run(kwargs: _ModeKwargs) -> SyncSummary:
    run_sync = cast("Any", _load_sync_attr("run_sync"))
    filter_posts_by_date = cast("Any", _load_sync_attr("filter_posts_by_date"))
    get_latest_post_date = cast("Any", _load_sync_attr("get_latest_post_date"))
    return run_sync(
        "profile",
        target_kind="profile",
        target_value=_required_str(kwargs, "username"),
        output_dir=_optional_path(kwargs, "output_dir"),
        limit=_optional_int(kwargs, "limit"),
        scrape_func=_profile_sync_scrape,
        get_posts_func=_load_profile_sync_posts,
        filter_by_date_func=filter_posts_by_date,
        get_latest_date_func=get_latest_post_date,
    )


def _hashtag_sync_run(kwargs: _ModeKwargs) -> SyncSummary:
    run_sync = cast("Any", _load_sync_attr("run_sync"))
    filter_posts_by_date = cast("Any", _load_sync_attr("filter_posts_by_date"))
    get_latest_post_date = cast("Any", _load_sync_attr("get_latest_post_date"))
    return run_sync(
        "hashtag",
        target_kind="hashtag",
        target_value=_required_str(kwargs, "hashtag"),
        output_dir=_optional_path(kwargs, "output_dir"),
        limit=_optional_int(kwargs, "limit"),
        scrape_func=_hashtag_sync_scrape,
        get_posts_func=_hashtag_sync_posts,
        filter_by_date_func=filter_posts_by_date,
        get_latest_date_func=get_latest_post_date,
    )


def _location_sync_run(kwargs: _ModeKwargs) -> SyncSummary:
    run_sync = cast("Any", _load_sync_attr("run_sync"))
    filter_posts_by_date = cast("Any", _load_sync_attr("filter_posts_by_date"))
    get_latest_post_date = cast("Any", _load_sync_attr("get_latest_post_date"))
    return run_sync(
        "location",
        target_kind="location",
        target_value=_required_str(kwargs, "location"),
        output_dir=_optional_path(kwargs, "output_dir"),
        limit=_optional_int(kwargs, "limit"),
        scrape_func=_location_sync_scrape,
        get_posts_func=_location_sync_posts,
        filter_by_date_func=filter_posts_by_date,
        get_latest_date_func=get_latest_post_date,
    )
