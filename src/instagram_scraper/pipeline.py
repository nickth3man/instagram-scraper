# Copyright (c) 2026
"""Unified provider dispatch for scrape subcommands."""

from __future__ import annotations

from pathlib import Path

from instagram_scraper.capabilities import ensure_mode_is_runnable
from instagram_scraper.models import RunSummary
from instagram_scraper.providers.follow_graph import FollowGraphProvider
from instagram_scraper.providers.hashtag import HashtagScrapeProvider
from instagram_scraper.providers.interactions import CommentersProvider, LikersProvider
from instagram_scraper.providers.location import LocationScrapeProvider
from instagram_scraper.providers.profile import ProfileScrapeProvider
from instagram_scraper.providers.stories import StoriesProvider
from instagram_scraper.providers.url import UrlScrapeProvider


def run_pipeline(mode: str, **kwargs: object) -> int:
    """Validate a mode and invoke the corresponding provider.

    Returns
    -------
    int
        Process exit code `0` when the selected mode runs successfully.

    Raises
    ------
    TypeError
        Raised when a provider does not return a `RunSummary`.

    """
    has_auth = bool(kwargs.get("has_auth"))
    ensure_mode_is_runnable(mode, has_auth=has_auth)
    summary = _run_mode(mode, kwargs)
    if not isinstance(summary, RunSummary):
        message = f"Provider for mode {mode} did not return RunSummary"
        raise TypeError(message)
    return 0


def _run_mode(mode: str, kwargs: dict[str, object]) -> RunSummary:
    summary: RunSummary
    if mode == "profile":
        summary = ProfileScrapeProvider.run(username=str(kwargs["username"]))
    elif mode == "url":
        summary = UrlScrapeProvider.run(post_url=str(kwargs["post_url"]))
    elif mode == "hashtag":
        summary = HashtagScrapeProvider.run(
            hashtag=str(kwargs["hashtag"]),
            limit=_optional_int(kwargs.get("limit")),
        )
    elif mode == "location":
        summary = LocationScrapeProvider.run(
            location=str(kwargs["location"]),
            limit=_optional_int(kwargs.get("limit")),
        )
    elif mode in {"followers", "following"}:
        summary = FollowGraphProvider.run(mode=mode)
    elif mode == "likers":
        summary = LikersProvider.run()
    elif mode == "commenters":
        summary = CommentersProvider.run()
    elif mode == "stories":
        summary = StoriesProvider.run()
    else:
        message = f"Unsupported mode: {mode}"
        raise ValueError(message)
    return summary


def default_output_dir(mode: str) -> Path:
    """Return the default output directory for a mode.

    Returns
    -------
    Path
        The mode-specific default output directory under `data/`.

    """
    return Path("data") / mode


def _optional_int(value: object) -> int | None:
    """Return an integer value when one was provided.

    Returns
    -------
    int | None
        The provided integer value, or `None` for any other type.

    """
    return value if isinstance(value, int) else None
