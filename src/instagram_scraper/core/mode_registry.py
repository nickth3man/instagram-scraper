# Copyright (c) 2026
"""Central registry for unified scrape modes.

This module keeps scrape-mode metadata, target resolution, execution hooks, and
GUI input parsing in one place so the CLI, pipeline, capabilities, and GUI do
not drift apart.
"""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from instagram_scraper.models import RunSummary, SyncSummary, TargetRecord

_ModeKwargs = dict[str, object]
_GuiValues = dict[str, Any]


class TargetResolver(Protocol):
    """Callable protocol for resolving normalized targets for a mode."""

    def __call__(self, kwargs: _ModeKwargs) -> list[TargetRecord]:
        """Resolve normalized targets for a scrape mode."""


class ModeRunner(Protocol):
    """Callable protocol for executing a scrape mode."""

    def __call__(self, kwargs: _ModeKwargs) -> RunSummary:
        """Execute a scrape mode and return a normalized summary."""


class GuiKwargsBuilder(Protocol):
    """Callable protocol for extracting mode-specific GUI kwargs."""

    def __call__(self, values: _GuiValues) -> _ModeKwargs:
        """Extract mode-specific keyword arguments from GUI form values."""


class SyncModeRunner(Protocol):
    """Callable protocol for executing a sync mode."""

    def __call__(self, kwargs: _ModeKwargs) -> SyncSummary:
        """Execute a sync mode and return a normalized summary."""


@dataclass(frozen=True, slots=True)
class ScrapeModeDefinition:
    """Definition of one scrape mode and its runtime hooks."""

    mode: str
    support_tier: str
    requires_auth: bool
    target_resolver: TargetResolver
    runner: ModeRunner
    gui_builder: GuiKwargsBuilder


@dataclass(frozen=True, slots=True)
class SyncModeDefinition:
    """Definition of one incremental sync mode and its runtime hooks."""

    mode: str
    support_tier: str
    requires_auth: bool
    target_resolver: TargetResolver
    runner: SyncModeRunner


class ModeInputError(ValueError):
    """Raised when GUI input for a scrape mode is invalid."""


def _load_attr(module_name: str, attr_name: str) -> object:
    module = import_module(module_name)
    return getattr(module, attr_name)


def _load_sync_attr(attr_name: str) -> object:
    return _load_attr("instagram_scraper.core.sync", attr_name)


def _required_str(kwargs: _ModeKwargs, key: str) -> str:
    value = kwargs.get(key)
    if isinstance(value, str):
        return value
    message = f"Expected string value for {key}"
    raise TypeError(message)


def _optional_str(kwargs: _ModeKwargs, key: str) -> str | None:
    value = kwargs.get(key)
    return value if isinstance(value, str) else None


def _optional_int(kwargs: _ModeKwargs, key: str) -> int | None:
    value = kwargs.get(key)
    return value if isinstance(value, int) else None


def _optional_float(kwargs: _ModeKwargs, key: str) -> float | None:
    value = kwargs.get(key)
    return value if isinstance(value, float) else None


def _optional_path(kwargs: _ModeKwargs, key: str) -> Path | None:
    value = kwargs.get(key)
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    message = f"Expected optional path-like value for {key}"
    raise TypeError(message)


def _path_arg(kwargs: _ModeKwargs, key: str) -> Path:
    value = kwargs.get(key)
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    message = f"Expected path-like value for {key}"
    raise TypeError(message)


def _required_text(values: _GuiValues, key: str, error_msg: str) -> str:
    raw_value = values.get(key, "")
    text = raw_value.strip() if isinstance(raw_value, str) else ""
    if text:
        return text
    raise ModeInputError(error_msg)


def _optional_text(values: _GuiValues, key: str) -> str | None:
    raw_value = values.get(key, "")
    if not isinstance(raw_value, str):
        return None
    text = raw_value.strip()
    return text or None


def _optional_gui_int(values: _GuiValues, key: str) -> int | None:
    raw_value = values.get(key, "")
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return None
        with suppress(ValueError):
            return int(text)
    return None


def _profile_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr(
        "instagram_scraper.providers.profile",
        "ProfileScrapeProvider",
        ),
    )
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(username=_required_str(kwargs, "username")),
    )


def _profile_run(kwargs: _ModeKwargs) -> RunSummary:
    provider = cast(
        "Any",
        _load_attr(
        "instagram_scraper.providers.profile",
        "ProfileScrapeProvider",
        ),
    )
    return cast(
        "RunSummary",
        provider.run(
            username=_required_str(kwargs, "username"),
            output_dir=_path_arg(kwargs, "output_dir"),
        ),
    )


def _url_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.url", "UrlScrapeProvider"),
    )
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(post_url=_required_str(kwargs, "post_url")),
    )


def _url_run(kwargs: _ModeKwargs) -> RunSummary:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.url", "UrlScrapeProvider"),
    )
    return cast(
        "RunSummary",
        provider.run(
            post_url=_required_str(kwargs, "post_url"),
            output_dir=_path_arg(kwargs, "output_dir"),
            cookie_header=_optional_str(kwargs, "cookie_header") or "",
            request_timeout=_optional_int(kwargs, "request_timeout") or 30,
            max_retries=_optional_int(kwargs, "max_retries") or 5,
            checkpoint_every=_optional_int(kwargs, "checkpoint_every") or 20,
            min_delay=_optional_float(kwargs, "min_delay") or 0.05,
            max_delay=_optional_float(kwargs, "max_delay") or 0.2,
        ),
    )


def _urls_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.url", "UrlScrapeProvider"),
    )
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(input_path=_path_arg(kwargs, "input_path")),
    )


def _urls_run(kwargs: _ModeKwargs) -> RunSummary:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.url", "UrlScrapeProvider"),
    )
    return cast(
        "RunSummary",
        provider.run_urls(
            input_path=_path_arg(kwargs, "input_path"),
            output_dir=_path_arg(kwargs, "output_dir"),
            cookie_header=_optional_str(kwargs, "cookie_header") or "",
            resume=bool(kwargs.get("resume")),
            reset_output=bool(kwargs.get("reset_output")),
            request_timeout=_optional_int(kwargs, "request_timeout") or 30,
            max_retries=_optional_int(kwargs, "max_retries") or 5,
            checkpoint_every=_optional_int(kwargs, "checkpoint_every") or 20,
            min_delay=_optional_float(kwargs, "min_delay") or 0.05,
            max_delay=_optional_float(kwargs, "max_delay") or 0.2,
        ),
    )


def _hashtag_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr(
        "instagram_scraper.providers.hashtag",
        "HashtagScrapeProvider",
        ),
    )
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(
            hashtag=_required_str(kwargs, "hashtag"),
            limit=_optional_int(kwargs, "limit"),
        ),
    )


def _hashtag_run(kwargs: _ModeKwargs) -> RunSummary:
    provider = cast(
        "Any",
        _load_attr(
        "instagram_scraper.providers.hashtag",
        "HashtagScrapeProvider",
        ),
    )
    return cast(
        "RunSummary",
        provider.run(
            hashtag=_required_str(kwargs, "hashtag"),
            limit=_optional_int(kwargs, "limit"),
            output_dir=_path_arg(kwargs, "output_dir"),
        ),
    )


def _location_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr(
        "instagram_scraper.providers.location",
        "LocationScrapeProvider",
        ),
    )
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(
            location=_required_str(kwargs, "location"),
            limit=_optional_int(kwargs, "limit"),
        ),
    )


def _location_run(kwargs: _ModeKwargs) -> RunSummary:
    provider = cast(
        "Any",
        _load_attr(
        "instagram_scraper.providers.location",
        "LocationScrapeProvider",
        ),
    )
    return cast(
        "RunSummary",
        provider.run(
            location=_required_str(kwargs, "location"),
            limit=_optional_int(kwargs, "limit"),
            output_dir=_path_arg(kwargs, "output_dir"),
        ),
    )


def _follow_targets(mode: str, kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr(
        "instagram_scraper.providers.follow_graph",
        "FollowGraphProvider",
        ),
    )
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(
            mode=mode,
            username=_required_str(kwargs, "username"),
            limit=_optional_int(kwargs, "limit"),
        ),
    )


def _follow_run(mode: str, kwargs: _ModeKwargs) -> RunSummary:
    provider = cast(
        "Any",
        _load_attr(
        "instagram_scraper.providers.follow_graph",
        "FollowGraphProvider",
        ),
    )
    return cast(
        "RunSummary",
        provider.run(
            mode=mode,
            username=_required_str(kwargs, "username"),
            limit=_optional_int(kwargs, "limit"),
            output_dir=_path_arg(kwargs, "output_dir"),
        ),
    )


def _interactions_provider(mode: str) -> object:
    provider_class = cast(
        "Any",
        _load_attr(
            "instagram_scraper.providers.interactions",
            "LikersProvider" if mode == "likers" else "CommentersProvider",
        ),
    )
    return provider_class()


def _optional_posts_limit(values: _GuiValues, mode: str) -> _ModeKwargs:
    posts_limit = _optional_gui_int(values, f"-{mode.upper()}-POSTS-LIMIT-")
    return {} if posts_limit is None else {"posts_limit": posts_limit}


def _interactions_targets(mode: str, kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast("Any", _interactions_provider(mode))
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(
            username=_required_str(kwargs, "username"),
            posts_limit=_optional_int(kwargs, "posts_limit"),
            limit=_optional_int(kwargs, "limit"),
        ),
    )


def _interactions_run(mode: str, kwargs: _ModeKwargs) -> RunSummary:
    provider = cast("Any", _interactions_provider(mode))
    return cast(
        "RunSummary",
        provider.run(
            username=_required_str(kwargs, "username"),
            posts_limit=_optional_int(kwargs, "posts_limit"),
            limit=_optional_int(kwargs, "limit"),
            output_dir=_path_arg(kwargs, "output_dir"),
        ),
    )


def _stories_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.stories", "StoriesProvider"),
    )
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(
            username=_optional_str(kwargs, "username"),
            hashtag=_optional_str(kwargs, "hashtag"),
            limit=_optional_int(kwargs, "limit"),
        ),
    )


def _stories_run(kwargs: _ModeKwargs) -> RunSummary:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.stories", "StoriesProvider"),
    )
    return cast(
        "RunSummary",
        provider.run(
            username=_optional_str(kwargs, "username"),
            hashtag=_optional_str(kwargs, "hashtag"),
            limit=_optional_int(kwargs, "limit"),
            output_dir=_path_arg(kwargs, "output_dir"),
        ),
    )


def _build_profile_gui_kwargs(values: _GuiValues) -> _ModeKwargs:
    return {
        "username": _required_text(
            values,
            "-PROFILE-USERNAME-",
            "Username is required for profile scraping.",
        ),
    }


def _build_url_gui_kwargs(values: _GuiValues) -> _ModeKwargs:
    return {
        "post_url": _required_text(
            values,
            "-URL-POST_URL-",
            "Post URL is required.",
        ),
    }


def _build_urls_gui_kwargs(values: _GuiValues) -> _ModeKwargs:
    return {
        "input_path": Path(
            _required_text(values, "-URLS-INPUT-", "Input file is required."),
        ),
        "resume": bool(values.get("-URLS-RESUME-", False)),
        "reset_output": bool(values.get("-URLS-RESET-OUTPUT-", False)),
    }


def _build_hashtag_gui_kwargs(values: _GuiValues) -> _ModeKwargs:
    return {
        "hashtag": _required_text(
            values,
            "-HASHTAG-HASHTAG-",
            "Hashtag is required.",
        ),
    }


def _build_location_gui_kwargs(values: _GuiValues) -> _ModeKwargs:
    return {
        "location": _required_text(
            values,
            "-LOCATION-LOCATION-",
            "Location is required.",
        ),
    }


def _build_follow_gui_kwargs(mode: str, values: _GuiValues) -> _ModeKwargs:
    return {
        "mode": mode,
        "username": _required_text(
            values,
            f"-{mode.upper()}-USERNAME-",
            f"Username is required for {mode} scraping.",
        ),
    }


def _build_interaction_gui_kwargs(mode: str, values: _GuiValues) -> _ModeKwargs:
    return {
        "mode": mode,
        "username": _required_text(
            values,
            f"-{mode.upper()}-USERNAME-",
            f"Username is required for {mode} scraping.",
        ),
        **_optional_posts_limit(values, mode),
    }


def _build_stories_gui_kwargs(values: _GuiValues) -> _ModeKwargs:
    use_username = bool(values.get("-STORIES-MODE-USERNAME-", True))
    if use_username:
        return {
            "username": _required_text(
                values,
                "-STORIES-USERNAME-",
                "Username is required for stories scraping.",
            ),
            "hashtag": None,
        }
    return {
        "username": None,
        "hashtag": _required_text(
            values,
            "-STORIES-HASHTAG-",
            "Hashtag is required for stories scraping.",
        ),
    }


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
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    posts = payload.get("posts") if isinstance(payload, dict) else None
    if not isinstance(posts, list):
        return []
    return [cast("dict[str, object]", post) for post in posts if isinstance(post, dict)]


def _profile_sync_scrape(
    *,
    target_value: str,
    output_dir: Path,
    **_: object,
) -> dict[str, int]:
    workflow = cast(
        "Any",
        _load_attr("instagram_scraper.workflows.profile", "run_profile_scrape"),
    )
    result = workflow(username=target_value, output_dir=output_dir)
    return {
        "posts": int(result.get("posts", 0)),
        "comments": int(result.get("comments", 0)),
        "errors": int(result.get("errors", 0)),
    }


def _synthetic_sync_posts(target_value: str, count: int) -> list[dict[str, object]]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        {
            "target_value": target_value,
            "date_utc": (base + timedelta(seconds=index)).isoformat(),
        }
        for index in range(count)
    ]


def _discovery_target_count(
    module_name: str,
    attr_name: str,
    arg_name: str,
    target_value: str,
    limit: int | None,
) -> int:
    provider = cast("Any", _load_attr(module_name, attr_name))
    targets = provider.resolve_targets(**{arg_name: target_value, "limit": limit})
    return len(targets)


def _hashtag_sync_scrape(
    *,
    target_value: str,
    limit: int | None,
    output_dir: Path,
    **_: object,
) -> dict[str, int]:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.hashtag", "HashtagScrapeProvider"),
    )
    summary = provider.run(hashtag=target_value, limit=limit, output_dir=output_dir)
    return {"errors": int(summary.errors)}


def _location_sync_scrape(
    *,
    target_value: str,
    limit: int | None,
    output_dir: Path,
    **_: object,
) -> dict[str, int]:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.location", "LocationScrapeProvider"),
    )
    summary = provider.run(location=target_value, limit=limit, output_dir=output_dir)
    return {"errors": int(summary.errors)}


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


SCRAPE_MODE_DEFINITIONS: dict[str, ScrapeModeDefinition] = {
    "profile": ScrapeModeDefinition(
        mode="profile",
        support_tier="stable",
        requires_auth=False,
        target_resolver=_profile_targets,
        runner=_profile_run,
        gui_builder=_build_profile_gui_kwargs,
    ),
    "url": ScrapeModeDefinition(
        mode="url",
        support_tier="stable",
        requires_auth=False,
        target_resolver=_url_targets,
        runner=_url_run,
        gui_builder=_build_url_gui_kwargs,
    ),
    "urls": ScrapeModeDefinition(
        mode="urls",
        support_tier="stable",
        requires_auth=False,
        target_resolver=_urls_targets,
        runner=_urls_run,
        gui_builder=_build_urls_gui_kwargs,
    ),
    "hashtag": ScrapeModeDefinition(
        mode="hashtag",
        support_tier="auth-required",
        requires_auth=True,
        target_resolver=_hashtag_targets,
        runner=_hashtag_run,
        gui_builder=_build_hashtag_gui_kwargs,
    ),
    "location": ScrapeModeDefinition(
        mode="location",
        support_tier="auth-required",
        requires_auth=True,
        target_resolver=_location_targets,
        runner=_location_run,
        gui_builder=_build_location_gui_kwargs,
    ),
    "followers": ScrapeModeDefinition(
        mode="followers",
        support_tier="experimental",
        requires_auth=True,
        target_resolver=lambda kwargs: _follow_targets("followers", kwargs),
        runner=lambda kwargs: _follow_run("followers", kwargs),
        gui_builder=lambda values: _build_follow_gui_kwargs("followers", values),
    ),
    "following": ScrapeModeDefinition(
        mode="following",
        support_tier="experimental",
        requires_auth=True,
        target_resolver=lambda kwargs: _follow_targets("following", kwargs),
        runner=lambda kwargs: _follow_run("following", kwargs),
        gui_builder=lambda values: _build_follow_gui_kwargs("following", values),
    ),
    "likers": ScrapeModeDefinition(
        mode="likers",
        support_tier="experimental",
        requires_auth=True,
        target_resolver=lambda kwargs: _interactions_targets("likers", kwargs),
        runner=lambda kwargs: _interactions_run("likers", kwargs),
        gui_builder=lambda values: _build_interaction_gui_kwargs("likers", values),
    ),
    "commenters": ScrapeModeDefinition(
        mode="commenters",
        support_tier="experimental",
        requires_auth=True,
        target_resolver=lambda kwargs: _interactions_targets("commenters", kwargs),
        runner=lambda kwargs: _interactions_run("commenters", kwargs),
        gui_builder=lambda values: _build_interaction_gui_kwargs("commenters", values),
    ),
    "stories": ScrapeModeDefinition(
        mode="stories",
        support_tier="auth-required",
        requires_auth=True,
        target_resolver=_stories_targets,
        runner=_stories_run,
        gui_builder=_build_stories_gui_kwargs,
    ),
}

GUI_SCRAPE_MODES: tuple[str, ...] = tuple(SCRAPE_MODE_DEFINITIONS.keys())

SYNC_MODE_DEFINITIONS: dict[str, SyncModeDefinition] = {
    "sync:profile": SyncModeDefinition(
        mode="sync:profile",
        support_tier="stable",
        requires_auth=False,
        target_resolver=_profile_sync_targets,
        runner=_profile_sync_run,
    ),
    "sync:hashtag": SyncModeDefinition(
        mode="sync:hashtag",
        support_tier="auth-required",
        requires_auth=True,
        target_resolver=_hashtag_sync_targets,
        runner=_hashtag_sync_run,
    ),
    "sync:location": SyncModeDefinition(
        mode="sync:location",
        support_tier="auth-required",
        requires_auth=True,
        target_resolver=_location_sync_targets,
        runner=_location_sync_run,
    ),
}


def is_registered_scrape_mode(mode: str) -> bool:
    """Return whether the given mode is handled by the scrape registry.

    Returns
    -------
    bool
        True when the mode is registered in ``SCRAPE_MODE_DEFINITIONS``.

    """
    return mode in SCRAPE_MODE_DEFINITIONS


def get_scrape_mode_definition(mode: str) -> ScrapeModeDefinition:
    """Return the registered scrape-mode definition.

    Returns
    -------
    ScrapeModeDefinition
        The centralized mode definition for the requested scrape mode.

    Raises
    ------
    ValueError
        If the mode is not registered.
    """
    definition = SCRAPE_MODE_DEFINITIONS.get(mode)
    if definition is None:
        message = f"Unsupported mode: {mode}"
        raise ValueError(message)
    return definition


def is_registered_sync_mode(mode: str) -> bool:
    """Return whether the given mode is handled by the sync registry.

    Returns
    -------
    bool
        True when the mode is registered in ``SYNC_MODE_DEFINITIONS``.

    """
    return mode in SYNC_MODE_DEFINITIONS


def get_sync_mode_definition(mode: str) -> SyncModeDefinition:
    """Return the registered sync-mode definition.

    Returns
    -------
    SyncModeDefinition
        The centralized mode definition for the requested sync mode.

    Raises
    ------
    ValueError
        If the mode is not registered.

    """
    definition = SYNC_MODE_DEFINITIONS.get(mode)
    if definition is None:
        message = f"Unsupported mode: {mode}"
        raise ValueError(message)
    return definition


def list_gui_scrape_modes() -> tuple[str, ...]:
    """Return scrape modes exposed by the desktop GUI.

    Returns
    -------
    tuple[str, ...]
        Ordered scrape mode names shown in the desktop GUI.

    """
    return GUI_SCRAPE_MODES
