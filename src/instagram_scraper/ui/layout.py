# Copyright (c) 2026
"""Window layout builders for the Instagram Scraper GUI."""

from __future__ import annotations

import FreeSimpleGUI

from instagram_scraper.core.mode_registry import list_gui_scrape_modes
from instagram_scraper.ui._tabs_shared import TAB_GROUP_KEY
from instagram_scraper.ui.tabs_primary import (
    create_hashtag_tab,
    create_location_tab,
    create_profile_tab,
    create_url_tab,
    create_urls_tab,
)
from instagram_scraper.ui.tabs_secondary import (
    create_commenters_tab,
    create_followers_tab,
    create_following_tab,
    create_likers_tab,
    create_stories_tab,
)

SCRAPE_MODES = list_gui_scrape_modes()


def create_shared_settings_column() -> FreeSimpleGUI.Column:
    """Create the shared settings column used across all scrape tabs.

    Returns
    -------
        Configured column containing shared scrape settings controls.
    """
    return FreeSimpleGUI.Column(
        [
            [FreeSimpleGUI.Text("Shared Settings", font=("Helvetica", 12, "bold"))],
            [FreeSimpleGUI.HorizontalSeparator()],
            [
                FreeSimpleGUI.Text("Output Directory:"),
                FreeSimpleGUI.Input(
                    key="-OUTPUT-DIR-",
                    default_text="data",
                    size=(40, 1),
                ),
                FreeSimpleGUI.FolderBrowse(),
            ],
            [
                FreeSimpleGUI.Text("Cookie Header:"),
                FreeSimpleGUI.Input(
                    key="-COOKIE-HEADER-",
                    default_text="",
                    size=(40, 1),
                    password_char=chr(42),
                ),
                FreeSimpleGUI.Button("Show", key="-TOGGLE-COOKIE-", size=(6, 1)),
            ],
            [
                FreeSimpleGUI.Text("Limit:"),
                FreeSimpleGUI.Input(
                    key="-LIMIT-",
                    default_text="",
                    size=(10, 1),
                    tooltip="Maximum items to scrape (empty = no limit)",
                ),
                FreeSimpleGUI.Text("Timeout:"),
                FreeSimpleGUI.Input(
                    key="-REQUEST-TIMEOUT-",
                    default_text="30",
                    size=(6, 1),
                ),
                FreeSimpleGUI.Text("Retries:"),
                FreeSimpleGUI.Input(
                    key="-MAX-RETRIES-",
                    default_text="5",
                    size=(6, 1),
                ),
            ],
            [FreeSimpleGUI.HorizontalSeparator()],
            [
                FreeSimpleGUI.Checkbox(
                    "Show Advanced Settings",
                    key="-SHOW-ADVANCED-",
                    enable_events=True,
                ),
            ],
            [
                FreeSimpleGUI.pin(
                    FreeSimpleGUI.Column(
                        [
                            [
                                FreeSimpleGUI.Text("Checkpoint Every:"),
                                FreeSimpleGUI.Input(
                                    key="-CHECKPOINT-EVERY-",
                                    default_text="20",
                                    size=(8, 1),
                                ),
                                FreeSimpleGUI.Checkbox(
                                    "Raw Captures",
                                    key="-RAW-CAPTURES-",
                                    default=False,
                                ),
                            ],
                            [
                                FreeSimpleGUI.Text("Min Delay:"),
                                FreeSimpleGUI.Input(
                                    key="-MIN-DELAY-",
                                    default_text="0.05",
                                    size=(8, 1),
                                ),
                                FreeSimpleGUI.Text("Max Delay:"),
                                FreeSimpleGUI.Input(
                                    key="-MAX-DELAY-",
                                    default_text="0.2",
                                    size=(8, 1),
                                ),
                            ],
                        ],
                        key="-ADVANCED-SETTINGS-COL-",
                        visible=False,
                    ),
                ),
            ],
            [FreeSimpleGUI.HorizontalSeparator()],
        ],
        pad=(10, 10),
    )


def create_main_window(
    *,
    start_event_prefix: str,
    stop_event_key: str,
    exit_event_key: str,
) -> FreeSimpleGUI.Window:
    """Create the main desktop window for the scraper GUI.

    Returns
    -------
        Finalized GUI window ready for the event loop.
    """
    tab_group = FreeSimpleGUI.TabGroup(
        [
            [
                create_profile_tab(start_event_prefix),
                create_url_tab(start_event_prefix),
                create_urls_tab(start_event_prefix),
                create_hashtag_tab(start_event_prefix),
                create_location_tab(start_event_prefix),
            ],
            [
                create_followers_tab(start_event_prefix),
                create_following_tab(start_event_prefix),
                create_likers_tab(start_event_prefix),
                create_commenters_tab(start_event_prefix),
                create_stories_tab(start_event_prefix),
            ],
        ],
        key=TAB_GROUP_KEY,
        enable_events=True,
    )

    layout = [
        [FreeSimpleGUI.Text("Instagram Scraper", font=("Helvetica", 16, "bold"))],
        [
            FreeSimpleGUI.Text(
                "Desktop GUI for scraping Instagram data",
                font=("Helvetica", 10),
            ),
        ],
        [FreeSimpleGUI.HorizontalSeparator()],
        [create_shared_settings_column()],
        [tab_group],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Text("Status:"),
            FreeSimpleGUI.Text(
                "Ready",
                key="-STATUS-TEXT-",
                size=(30, 1),
                text_color="green",
            ),
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button(
                "Stop",
                key=stop_event_key,
                button_color=("white", "#C62828"),
                disabled=True,
            ),
        ],
        [
            FreeSimpleGUI.ProgressBar(
                100,
                orientation="h",
                size=(60, 20),
                key="-PROGRESS-BAR-",
            ),
        ],
        [FreeSimpleGUI.Text("Log Output:", font=("Helvetica", 10, "bold"))],
        [
            FreeSimpleGUI.Multiline(
                key="-LOG-OUTPUT-",
                size=(80, 15),
                disabled=True,
                autoscroll=True,
                reroute_stdout=True,
                reroute_stderr=True,
                echo_stdout_stderr=True,
            ),
        ],
        [FreeSimpleGUI.HorizontalSeparator()],
        [
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button("Clear Log", key="-CLEAR-LOG-"),
            FreeSimpleGUI.Button("Exit", key=exit_event_key),
        ],
    ]

    return FreeSimpleGUI.Window(
        "Instagram Scraper GUI",
        layout,
        resizable=True,
        finalize=True,
        size=(900, 800),
    )
