# Copyright (c) 2026
"""Scrape-mode target, runner, and GUI helper implementations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from instagram_scraper.core.mode_helpers import (
    _GuiValues,
    _load_attr,
    _ModeKwargs,
    _optional_float,
    _optional_gui_int,
    _optional_int,
    _optional_path,
    _optional_str,
    _path_arg,
    _required_str,
    _required_text,
)

if TYPE_CHECKING:
    from instagram_scraper.models import RunSummary, TargetRecord


def _profile_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.profile", "ProfileScrapeProvider"),
    )
    return cast(
        "list[TargetRecord]",
        provider.resolve_targets(username=_required_str(kwargs, "username")),
    )


def _profile_run(kwargs: _ModeKwargs) -> RunSummary:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.profile", "ProfileScrapeProvider"),
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
            cookie_header=(
                _optional_str(kwargs, "cookie_header")
                if _optional_str(kwargs, "cookie_header") is not None
                else ""
            ),
            request_timeout=(
                _optional_int(kwargs, "request_timeout")
                if _optional_int(kwargs, "request_timeout") is not None
                else 30
            ),
            max_retries=(
                _optional_int(kwargs, "max_retries")
                if _optional_int(kwargs, "max_retries") is not None
                else 5
            ),
            checkpoint_every=(
                _optional_int(kwargs, "checkpoint_every")
                if _optional_int(kwargs, "checkpoint_every") is not None
                else 20
            ),
            min_delay=(
                _optional_float(kwargs, "min_delay")
                if _optional_float(kwargs, "min_delay") is not None
                else 0.05
            ),
            max_delay=(
                _optional_float(kwargs, "max_delay")
                if _optional_float(kwargs, "max_delay") is not None
                else 0.2
            ),
            browser_html=bool(kwargs.get("browser_html", False)),
            cookies_file=_optional_path(kwargs, "cookies_file"),
            storage_state=_optional_path(kwargs, "storage_state"),
            user_data_dir=_optional_path(kwargs, "user_data_dir"),
            headed=bool(kwargs.get("headed", False)),
            timeout_ms=(
                _optional_int(kwargs, "timeout_ms")
                if _optional_int(kwargs, "timeout_ms") is not None
                else 30000
            ),
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
            cookie_header=(
                _optional_str(kwargs, "cookie_header")
                if _optional_str(kwargs, "cookie_header") is not None
                else ""
            ),
            resume=bool(kwargs.get("resume")),
            reset_output=bool(kwargs.get("reset_output")),
            request_timeout=(
                _optional_int(kwargs, "request_timeout")
                if _optional_int(kwargs, "request_timeout") is not None
                else 30
            ),
            max_retries=(
                _optional_int(kwargs, "max_retries")
                if _optional_int(kwargs, "max_retries") is not None
                else 5
            ),
            checkpoint_every=(
                _optional_int(kwargs, "checkpoint_every")
                if _optional_int(kwargs, "checkpoint_every") is not None
                else 20
            ),
            min_delay=(
                _optional_float(kwargs, "min_delay")
                if _optional_float(kwargs, "min_delay") is not None
                else 0.05
            ),
            max_delay=(
                _optional_float(kwargs, "max_delay")
                if _optional_float(kwargs, "max_delay") is not None
                else 0.2
            ),
            browser_html=bool(kwargs.get("browser_html", False)),
            cookies_file=_optional_path(kwargs, "cookies_file"),
            storage_state=_optional_path(kwargs, "storage_state"),
            user_data_dir=_optional_path(kwargs, "user_data_dir"),
            headed=bool(kwargs.get("headed", False)),
            timeout_ms=(
                _optional_int(kwargs, "timeout_ms")
                if _optional_int(kwargs, "timeout_ms") is not None
                else 30000
            ),
        ),
    )


def _hashtag_targets(kwargs: _ModeKwargs) -> list[TargetRecord]:
    provider = cast(
        "Any",
        _load_attr("instagram_scraper.providers.hashtag", "HashtagScrapeProvider"),
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
        _load_attr("instagram_scraper.providers.hashtag", "HashtagScrapeProvider"),
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
        _load_attr("instagram_scraper.providers.location", "LocationScrapeProvider"),
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
        _load_attr("instagram_scraper.providers.location", "LocationScrapeProvider"),
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
    provider_class = cast(
        "Any",
        _load_attr("instagram_scraper.providers.follow_graph", "FollowGraphProvider"),
    )
    return cast(
        "list[TargetRecord]",
        provider_class().resolve_targets(
            mode=mode,
            username=_required_str(kwargs, "username"),
            limit=_optional_int(kwargs, "limit"),
        ),
    )


def _follow_run(mode: str, kwargs: _ModeKwargs) -> RunSummary:
    provider_class = cast(
        "Any",
        _load_attr("instagram_scraper.providers.follow_graph", "FollowGraphProvider"),
    )
    return cast(
        "RunSummary",
        provider_class().run(
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
        "post_url": _required_text(values, "-URL-POST_URL-", "Post URL is required."),
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
        "hashtag": _required_text(values, "-HASHTAG-HASHTAG-", "Hashtag is required."),
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
