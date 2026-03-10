# Copyright (c) 2026
"""Capability preflight checks for unified scrape modes."""

from instagram_scraper.models import ModeDescriptor

SUPPORT_TIER_BY_MODE = {
    "profile": "stable",
    "url": "stable",
    "urls": "stable",
    "hashtag": "auth-required",
    "location": "auth-required",
    "stories": "auth-required",
    "followers": "experimental",
    "following": "experimental",
    "likers": "experimental",
    "commenters": "experimental",
    "sync:profile": "stable",
    "sync:hashtag": "auth-required",
    "sync:location": "auth-required",
}

AUTH_REQUIRED_MODES = {
    mode
    for mode, tier in SUPPORT_TIER_BY_MODE.items()
    if tier in {"auth-required", "experimental"}
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
