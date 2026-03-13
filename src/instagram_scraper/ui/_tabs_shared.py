# Copyright (c) 2026
"""Shared tab keys and small UI builders.

The GUI uses string keys for tab selection and event routing. Centralizing them
avoids drift between `layout.py` and the individual tab builder modules.
"""

from __future__ import annotations

import FreeSimpleGUI

Layout = list[list[FreeSimpleGUI.Element]]
Element = FreeSimpleGUI.Element


TAB_GROUP_KEY: str = "-TAB-GROUP-"

TAB_PROFILE: str = "-TAB-PROFILE-"
TAB_URL: str = "-TAB-URL-"
TAB_URLS: str = "-TAB-URLS-"
TAB_HASHTAG: str = "-TAB-HASHTAG-"
TAB_LOCATION: str = "-TAB-LOCATION-"

TAB_FOLLOWERS: str = "-TAB-FOLLOWERS-"
TAB_FOLLOWING: str = "-TAB-FOLLOWING-"
TAB_LIKERS: str = "-TAB-LIKERS-"
TAB_COMMENTERS: str = "-TAB-COMMENTERS-"
TAB_STORIES: str = "-TAB-STORIES-"


def create_start_scrape_button(
    start_event_prefix: str,
    mode: str,
) -> FreeSimpleGUI.Button:
    """Create a consistent start button for a scrape mode.

    Returns
    -------
        A configured Button element with the scrape event key.
    """
    return FreeSimpleGUI.Button(
        "Start Scrape",
        key=f"{start_event_prefix}{mode}",
        button_color=("white", "#2E7D32"),
        size=(15, 1),
    )


def create_tab(
    title: str,
    layout: Layout,
    *,
    key: str,
) -> FreeSimpleGUI.Tab:
    """Create a tab with a stable key.

    Returns
    -------
        A Tab element with the given title, layout, and key.
    """
    return FreeSimpleGUI.Tab(title, layout, key=key)
