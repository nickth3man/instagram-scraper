# Copyright (c) 2026
"""Filtering helpers for normalized scrape targets."""


def should_keep_user(user: dict[str, object], *, skip_private: bool) -> bool:
    """Return whether a discovered user passes the configured filters.

    Returns
    -------
    bool
        `True` when the user should be retained for downstream processing.

    """
    return not (skip_private and user.get("is_private") is True)
