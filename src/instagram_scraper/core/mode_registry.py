# Copyright (c) 2026
"""Central registry for unified scrape modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from instagram_scraper.core.mode_definitions import (
    _build_follow_gui_kwargs,
    _build_hashtag_gui_kwargs,
    _build_interaction_gui_kwargs,
    _build_location_gui_kwargs,
    _build_profile_gui_kwargs,
    _build_stories_gui_kwargs,
    _build_url_gui_kwargs,
    _build_urls_gui_kwargs,
    _follow_run,
    _follow_targets,
    _hashtag_run,
    _hashtag_targets,
    _interactions_run,
    _interactions_targets,
    _location_run,
    _location_targets,
    _profile_run,
    _profile_targets,
    _stories_run,
    _stories_targets,
    _url_run,
    _url_targets,
    _urls_run,
    _urls_targets,
)
from instagram_scraper.core.sync_definitions import (
    _hashtag_sync_run,
    _hashtag_sync_targets,
    _location_sync_run,
    _location_sync_targets,
    _profile_sync_run,
    _profile_sync_targets,
)

if TYPE_CHECKING:
    from instagram_scraper.models import RunSummary, SyncSummary, TargetRecord

_ModeKwargs = dict[str, object]
_GuiValues = dict[str, object]


class ModeInputError(ValueError):
    """Raised when mode input validation fails."""


class TargetResolver(Protocol):
    """Callable protocol for resolving normalized targets for a mode."""

    def __call__(self, kwargs: _ModeKwargs) -> list[TargetRecord]:
        """Resolve targets from kwargs."""
        ...


class ModeRunner(Protocol):
    """Callable protocol for executing a scrape mode."""

    def __call__(self, kwargs: _ModeKwargs) -> RunSummary:
        """Execute scrape mode."""
        ...


class GuiKwargsBuilder(Protocol):
    """Callable protocol for extracting GUI kwargs for a mode."""

    def __call__(self, values: _GuiValues) -> _ModeKwargs:
        """Extract kwargs from GUI values."""
        ...


class SyncModeRunner(Protocol):
    """Callable protocol for executing an incremental sync mode."""

    def __call__(self, kwargs: _ModeKwargs) -> SyncSummary:
        """Execute sync mode."""
        ...


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
    """Definition of one sync mode and its runtime hooks."""

    mode: str
    support_tier: str
    requires_auth: bool
    target_resolver: TargetResolver
    runner: SyncModeRunner


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
        True if mode is registered, False otherwise.
    """
    return mode in SCRAPE_MODE_DEFINITIONS


def get_scrape_mode_definition(mode: str) -> ScrapeModeDefinition:
    """Return the registered scrape-mode definition.

    Args:
        mode: The scrape mode to get.

    Returns
    -------
        The scrape mode definition.

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
        True if mode is registered, False otherwise.
    """
    return mode in SYNC_MODE_DEFINITIONS


def get_sync_mode_definition(mode: str) -> SyncModeDefinition:
    """Return the registered sync-mode definition.

    Args:
        mode: The sync mode to get.

    Returns
    -------
        The sync mode definition.

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
        Tuple of GUI-exposed scrape mode names.
    """
    return GUI_SCRAPE_MODES
