# Copyright (c) 2026
"""Window layout builders for the Instagram Scraper GUI."""

from __future__ import annotations

import FreeSimpleGUI

from instagram_scraper.core.mode_registry import list_gui_scrape_modes

SCRAPE_MODES = list_gui_scrape_modes()

TAB_PROFILE = "-TAB-PROFILE-"
TAB_URL = "-TAB-URL-"
TAB_URLS = "-TAB-URLS-"
TAB_HASHTAG = "-TAB-HASHTAG-"
TAB_LOCATION = "-TAB-LOCATION-"
TAB_FOLLOWERS = "-TAB-FOLLOWERS-"
TAB_FOLLOWING = "-TAB-FOLLOWING-"
TAB_LIKERS = "-TAB-LIKERS-"
TAB_COMMENTERS = "-TAB-COMMENTERS-"
TAB_STORIES = "-TAB-STORIES-"


def _start_scrape_button(
    start_event_prefix: str,
    mode: str,
) -> FreeSimpleGUI.Button:
    return FreeSimpleGUI.Button(
        "Start Scrape",
        key=f"{start_event_prefix}{mode}",
        button_color=("white", "#2E7D32"),
        size=(15, 1),
    )


def create_shared_settings_column() -> FreeSimpleGUI.Column:
    """Create the column for shared settings.

    Returns
    -------
    sg.Column
        The shared settings column element.

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


def create_profile_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the Profile scrape tab.

    Returns
    -------
    sg.Tab
        The profile scrape tab element.

    """
    layout = [
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
        [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "profile")],
    ]
    return FreeSimpleGUI.Tab("Profile", layout, key=TAB_PROFILE)


def create_url_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the single URL scrape tab.

    Returns
    -------
    sg.Tab
        The single-URL scrape tab element.

    """
    layout = [
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
        [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "url")],
    ]
    return FreeSimpleGUI.Tab("Single URL", layout, key=TAB_URL)


def create_urls_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the multiple URLs scrape tab.

    Returns
    -------
    sg.Tab
        The multi-URL scrape tab element.

    """
    layout = [
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
        [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "urls")],
    ]
    return FreeSimpleGUI.Tab("Multiple URLs", layout, key=TAB_URLS)


def create_hashtag_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the Hashtag scrape tab.

    Returns
    -------
    sg.Tab
        The hashtag scrape tab element.

    """
    layout = [
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
        [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "hashtag")],
    ]
    return FreeSimpleGUI.Tab("Hashtag", layout, key=TAB_HASHTAG)


def create_location_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the Location scrape tab.

    Returns
    -------
    sg.Tab
        The location scrape tab element.

    """
    layout = [
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
        [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "location")],
    ]
    return FreeSimpleGUI.Tab("Location", layout, key=TAB_LOCATION)


def create_followers_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the Followers scrape tab.

    Returns
    -------
    sg.Tab
        The followers scrape tab element.

    """
    layout = [
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
        [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "followers")],
    ]
    return FreeSimpleGUI.Tab("Followers", layout, key=TAB_FOLLOWERS)


def create_following_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the Following scrape tab.

    Returns
    -------
    sg.Tab
        The following scrape tab element.

    """
    layout = [
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
        [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "following")],
    ]
    return FreeSimpleGUI.Tab("Following", layout, key=TAB_FOLLOWING)


def create_likers_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the Likers scrape tab.

    Returns
    -------
    sg.Tab
        The likers scrape tab element.

    """
    layout = [
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
        [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "likers")],
    ]
    return FreeSimpleGUI.Tab("Likers", layout, key=TAB_LIKERS)


def create_commenters_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the Commenters scrape tab.

    Returns
    -------
    sg.Tab
        The commenters scrape tab element.

    """
    layout = [
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
            _start_scrape_button(start_event_prefix, "commenters"),
        ],
    ]
    return FreeSimpleGUI.Tab("Commenters", layout, key=TAB_COMMENTERS)


def create_stories_tab(start_event_prefix: str) -> FreeSimpleGUI.Tab:
    """Create the Stories scrape tab.

    Returns
    -------
    sg.Tab
        The stories scrape tab element.

    """
    return FreeSimpleGUI.Tab(
        "Stories",
        [
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
            [FreeSimpleGUI.Push(), _start_scrape_button(start_event_prefix, "stories")],
        ],
        key=TAB_STORIES,
    )


def create_main_window(
    *,
    start_event_prefix: str,
    stop_event_key: str,
    exit_event_key: str,
) -> FreeSimpleGUI.Window:
    """Create and return the main application window.

    Returns
    -------
    sg.Window
        The main GUI window.

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
        key="-TAB-GROUP-",
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
