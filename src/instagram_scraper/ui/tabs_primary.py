# Copyright (c) 2026
"""Primary tab creators for Instagram Scraper GUI.

This module contains tab creation functions for profile, URL, URLs, hashtag,
and location scraping modes.
"""

from __future__ import annotations

import FreeSimpleGUI

from instagram_scraper.ui._tabs_shared import (
    TAB_HASHTAG,
    TAB_LOCATION,
    TAB_PROFILE,
    TAB_URL,
    TAB_URLS,
    Element,
    create_start_scrape_button,
    create_tab,
)


def create_profile_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the profile scrape tab.

    Returns
    -------
        Configured tab for profile scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Profile Scraper", font=("Helvetica", 14, "bold"))],
        [
            FreeSimpleGUI.Text(
                "Scrape posts and comments from a public Instagram profile.",
            ),
        ],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Username:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-PROFILE-USERNAME-",
                size=(30, 1),
                tooltip="Instagram username (without @)",
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "profile"),
        ],
    ]
    return create_tab("Profile", layout, key=TAB_PROFILE)


def create_url_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the single-URL scrape tab.

    Returns
    -------
        Configured tab for single-URL scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Single URL Scraper", font=("Helvetica", 14, "bold"))],
        [FreeSimpleGUI.Text("Scrape a single Instagram post by URL.")],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Post URL:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-URL-POST_URL-",
                size=(50, 1),
                tooltip="Full Instagram post URL",
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "url"),
        ],
    ]
    return create_tab("Single URL", layout, key=TAB_URL)


def create_urls_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the multi-URL scrape tab.

    Returns
    -------
        Configured tab for bulk URL scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Multiple URLs Scraper", font=("Helvetica", 14, "bold"))],
        [FreeSimpleGUI.Text("Scrape multiple Instagram posts from a JSON file.")],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Input File:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-URLS-INPUT-",
                size=(40, 1),
                tooltip="JSON file with 'urls' array",
            ),
            FreeSimpleGUI.FileBrowse(file_types=(("JSON Files", "*.json"),)),
        ],
        [
            FreeSimpleGUI.Checkbox(
                "Resume from checkpoint",
                key="-URLS-RESUME-",
                default=False,
            ),
            FreeSimpleGUI.Checkbox(
                "Reset output files",
                key="-URLS-RESET-OUTPUT-",
                default=False,
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "urls"),
        ],
    ]
    return create_tab("Multiple URLs", layout, key=TAB_URLS)


def create_hashtag_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the hashtag scrape tab.

    Returns
    -------
        Configured tab for hashtag scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Hashtag Scraper", font=("Helvetica", 14, "bold"))],
        [FreeSimpleGUI.Text("Scrape posts by hashtag (requires authentication).")],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Hashtag:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-HASHTAG-HASHTAG-",
                size=(30, 1),
                tooltip="Hashtag without #",
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "hashtag"),
        ],
    ]
    return create_tab("Hashtag", layout, key=TAB_HASHTAG)


def create_location_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the location scrape tab.

    Returns
    -------
        Configured tab for location scraping.
    """
    layout: list[list[Element]] = [
        [FreeSimpleGUI.Text("Location Scraper", font=("Helvetica", 14, "bold"))],
        [FreeSimpleGUI.Text("Scrape posts by location (requires authentication).")],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Location:*", size=(12, 1)),
            FreeSimpleGUI.Input(
                key="-LOCATION-LOCATION-",
                size=(30, 1),
                tooltip="Location name or ID",
            ),
        ],
        [
            FreeSimpleGUI.Push(),
            create_start_scrape_button(start_event_prefix, "location"),
        ],
    ]
    return create_tab("Location", layout, key=TAB_LOCATION)
