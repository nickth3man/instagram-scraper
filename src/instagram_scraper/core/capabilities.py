# Copyright (c) 2026
"""Capability preflight checks for unified scrape and sync modes."""

from instagram_scraper.core.mode_registry import (
    SCRAPE_MODE_DEFINITIONS,
    SYNC_MODE_DEFINITIONS,
)
from instagram_scraper.models import ModeDescriptor

SUPPORT_TIER_BY_MODE = {
    **{
        mode: definition.support_tier
        for mode, definition in SCRAPE_MODE_DEFINITIONS.items()
    },
    **{
        mode: definition.support_tier
        for mode, definition in SYNC_MODE_DEFINITIONS.items()
    },
}

AUTH_REQUIRED_MODES = {
    *(
        mode
        for mode, definition in SCRAPE_MODE_DEFINITIONS.items()
        if definition.requires_auth
    ),
    *(
        mode
        for mode, definition in SYNC_MODE_DEFINITIONS.items()
        if definition.requires_auth
    ),
}


def describe_mode_capability(mode: str) -> ModeDescriptor:
    """Describe the support tier and auth requirement for a mode.

    Returns
    -------
    ModeDescriptor
        Support metadata for the requested mode.

    Raises
    ------
    ValueError
        Raised when the mode is unknown.

    """
    support_tier = SUPPORT_TIER_BY_MODE.get(mode)
    if support_tier is None:
        message = f"Unsupported mode: {mode}"
        raise ValueError(message)
    return ModeDescriptor(
        mode=mode,
        support_tier=support_tier,
        requires_auth=mode in AUTH_REQUIRED_MODES,
    )


def ensure_mode_is_runnable(mode: str, *, has_auth: bool) -> None:
    """Raise when the selected mode requires authentication.

    Raises
    ------
    RuntimeError
        Raised when the selected mode needs authentication but none is present.

    """
    if mode in AUTH_REQUIRED_MODES and not has_auth:
        message = f"{mode} requires authentication"
        raise RuntimeError(message)
