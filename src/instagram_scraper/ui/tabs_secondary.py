# Copyright (c) 2026
"""Secondary tab creators for Instagram Scraper GUI.

This module contains tab creation functions for followers, following, likers,
commenters, and stories scraping modes.
"""

from __future__ import annotations

import FreeSimpleGUI

from instagram_scraper.ui._tabs_shared import (
    TAB_COMMENTERS,
    TAB_FOLLOWERS,
    TAB_FOLLOWING,
    TAB_LIKERS,
    TAB_STORIES,
    Element,
    create_start_scrape_button,
    create_tab,
)


def create_followers_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the followers scrape tab.

    Returns
    -------
        Configured tab for followers scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Followers Scraper", font=("Helvetica", 14, "bold"))],
        [FreeSimpleGUI.Text("Discover followers of a user (requires authentication).")],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Username:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-FOLLOWERS-USERNAME-",
                size=(30, 1),
                tooltip="Target Instagram username",
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "followers"),
        ],
    ]
    return create_tab("Followers", layout, key=TAB_FOLLOWERS)


def create_following_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the following scrape tab.

    Returns
    -------
        Configured tab for following scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Following Scraper", font=("Helvetica", 14, "bold"))],
        [FreeSimpleGUI.Text("Discover who a user follows (requires authentication).")],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Username:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-FOLLOWING-USERNAME-",
                size=(30, 1),
                tooltip="Target Instagram username",
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "following"),
        ],
    ]
    return create_tab("Following", layout, key=TAB_FOLLOWING)


def create_likers_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the likers scrape tab.

    Returns
    -------
        Configured tab for likers scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Likers Scraper", font=("Helvetica", 14, "bold"))],
        [
            FreeSimpleGUI.Text(
                "Discover users who liked posts (requires authentication).",
            ),
        ],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Username:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-LIKERS-USERNAME-",
                size=(30, 1),
                tooltip="Target Instagram username",
            ),
        ],
        [
            FreeSimpleGUI.Text("Posts Limit:"),
            FreeSimpleGUI.Input(
                key="-LIKERS-POSTS-LIMIT-",
                default_text="",
                size=(10, 1),
                tooltip="Max posts to check for likes",
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "likers"),
        ],
    ]
    return create_tab("Likers", layout, key=TAB_LIKERS)


def create_commenters_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the commenters scrape tab.

    Returns
    -------
        Configured tab for commenters scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Commenters Scraper", font=("Helvetica", 14, "bold"))],
        [
            FreeSimpleGUI.Text(
                "Discover users who commented on posts (requires authentication).",
            ),
        ],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Username:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-COMMENTERS-USERNAME-",
                size=(30, 1),
                tooltip="Target Instagram username",
            ),
        ],
        [
            FreeSimpleGUI.Text("Posts Limit:"),
            FreeSimpleGUI.Input(
                key="-COMMENTERS-POSTS-LIMIT-",
                default_text="",
                size=(10, 1),
                tooltip="Max posts to check for comments",
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "commenters"),
        ],
    ]
    return create_tab("Commenters", layout, key=TAB_COMMENTERS)


def create_stories_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the stories scrape tab.

    Returns
    -------
        Configured tab for stories scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Stories Scraper", font=("Helvetica", 14, "bold"))],
        [
            FreeSimpleGUI.Text(
                "Scrape stories by username or hashtag (requires authentication).",
            ),
        ],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Radio(
                "By Username",
                "STORIES_MODE",
                key="-STORIES-MODE-USERNAME-",
                default=True,
                enable_events=True,
            ),
            FreeSimpleGUI.Radio(
                "By Hashtag",
                "STORIES_MODE",
                key="-STORIES-MODE-HASHTAG-",
                enable_events=True,
            ),
        ],
        [
            FreeSimpleGUI.pin(
                FreeSimpleGUI.Column(
                    [
                        [
                            FreeSimpleGUI.Text("Username:*", size=(12, 1)),
                            FreeSimpleGUI.Input(
                                key="-STORIES-USERNAME-",
                                size=(30, 1),
                            ),
                        ],
                    ],
                    key="-STORIES-USERNAME-COL-",
                ),
            ),
        ],
        [
            FreeSimpleGUI.pin(
                FreeSimpleGUI.Column(
                    [
                        [
                            FreeSimpleGUI.Text("Hashtag:*", size=(12, 1)),
                            FreeSimpleGUI.Input(
                                key="-STORIES-HASHTAG-",
                                size=(30, 1),
                            ),
                        ],
                    ],
                    key="-STORIES-HASHTAG-COL-",
                    visible=False,
                ),
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "stories"),
        ],
    ]
    return create_tab("Stories", layout, key=TAB_STORIES)
