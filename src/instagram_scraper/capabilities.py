# Copyright (c) 2026
"""Capability preflight checks for unified scrape modes."""

AUTH_REQUIRED_MODES = {
    "hashtag",
    "location",
    "followers",
    "following",
    "likers",
    "commenters",
    "stories",
}


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
