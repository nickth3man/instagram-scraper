# Copyright (c) 2026
"""Desktop GUI for Instagram Scraper using FreeSimpleGUI."""

from __future__ import annotations

import contextlib
import threading
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

import FreeSimpleGUI

if TYPE_CHECKING:
    from collections.abc import Callable

from instagram_scraper.capabilities import (
    AUTH_REQUIRED_MODES,
    describe_mode_capability,
)
from instagram_scraper.config import HttpConfig, OutputConfig, ScraperConfig
from instagram_scraper.exceptions import (
    AuthenticationError,
    InstagramError,
    NetworkError,
    RateLimitError,
)
from instagram_scraper.logging_config import get_logger
from instagram_scraper.pipeline import PipelineCancelledError, execute_pipeline

logger = get_logger(__name__)

# Theme and styling
FreeSimpleGUI.theme("DarkGrey13")

# Event keys
EVENT_EXIT = "-EXIT-"
EVENT_START_SCRAPE = "-START-SCRAPE-"
EVENT_STOP_SCRAPE = "-STOP-SCRAPE-"
EVENT_SCRAPE_COMPLETE = "-SCRAPE-COMPLETE-"
EVENT_SCRAPE_ERROR = "-SCRAPE-ERROR-"
EVENT_LOG_UPDATE = "-LOG-UPDATE-"
EVENT_PROGRESS_UPDATE = "-PROGRESS-UPDATE-"

# Tab keys
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


class ScraperWorker:
    """Background worker for running scrapes without blocking the GUI."""

    def __init__(self, window: FreeSimpleGUI.Window) -> None:
        """Initialize the scraper worker.

        Parameters
        ----------
        window : sg.Window
            The main GUI window for event communication.

        """
        self.window = window
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start_scrape(self, mode: str, kwargs: dict[str, Any]) -> None:
        """Start a scrape operation in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._scrape_thread,
            args=(mode, kwargs),
            daemon=True,
        )
        self._thread.start()

    def _scrape_thread(self, mode: str, kwargs: dict[str, Any]) -> None:
        """Thread target that runs the scrape and reports results."""

        def progress_callback(current: int, total: int) -> None:
            self.window.write_event_value(EVENT_PROGRESS_UPDATE, (current, total))

        try:
            summary = execute_pipeline(
                mode,
                cancellation_event=self._stop_event,
                progress_callback=progress_callback,
                **kwargs,
            )
            self.window.write_event_value(
                EVENT_SCRAPE_COMPLETE,
                {"success": True, "summary": summary.model_dump()},
            )
        except PipelineCancelledError:
            self.window.write_event_value(
                EVENT_SCRAPE_ERROR,
                {
                    "error": "Scrape was cancelled by user",
                    "detail": "",
                    "cancelled": True,
                },
            )
        except RateLimitError as exc:
            retry_msg = (
                f" Wait {exc.retry_after}s before retrying." if exc.retry_after else ""
            )
            self.window.write_event_value(
                EVENT_SCRAPE_ERROR,
                {
                    "error": f"Rate limit exceeded.{retry_msg}",
                    "detail": traceback.format_exc(),
                    "error_type": "rate_limit",
                    "retry_after": exc.retry_after,
                },
            )
        except AuthenticationError as exc:
            self.window.write_event_value(
                EVENT_SCRAPE_ERROR,
                {
                    "error": f"Authentication failed: {exc}",
                    "detail": traceback.format_exc(),
                    "error_type": "authentication",
                },
            )
        except NetworkError as exc:
            self.window.write_event_value(
                EVENT_SCRAPE_ERROR,
                {
                    "error": f"Network error: {exc}",
                    "detail": traceback.format_exc(),
                    "error_type": "network",
                },
            )
        except InstagramError as exc:
            self.window.write_event_value(
                EVENT_SCRAPE_ERROR,
                {
                    "error": f"{type(exc).__name__}: {exc}",
                    "detail": traceback.format_exc(),
                    "error_type": "instagram",
                },
            )
        except Exception as exc:  # noqa: BLE001
            error_msg = f"{type(exc).__name__}: {exc}"
            error_detail = traceback.format_exc()
            self.window.write_event_value(
                EVENT_SCRAPE_ERROR,
                {"error": error_msg, "detail": error_detail, "error_type": "unknown"},
            )

    def request_stop(self) -> None:
        """Request the worker to stop (best effort)."""
        self._stop_event.set()

    def is_running(self) -> bool:
        """Check if a scrape is currently running.

        Returns
        -------
        bool
            True if a scrape thread is active, False otherwise.

        """
        return self._thread is not None and self._thread.is_alive()


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
                    password_char="*",  # noqa: S106
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


def create_profile_tab() -> FreeSimpleGUI.Tab:
    """Create the Profile scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for profile scraping.

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
        [
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}profile",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Profile", layout, key=TAB_PROFILE)


def create_url_tab() -> FreeSimpleGUI.Tab:
    """Create the single URL scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for single URL scraping.

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
        [
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}url",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Single URL", layout, key=TAB_URL)


def create_urls_tab() -> FreeSimpleGUI.Tab:
    """Create the multiple URLs scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for multiple URLs scraping.

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
            FreeSimpleGUI.FileBrowse(file_types=("JSON Files", "*.json")),
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
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}urls",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Multiple URLs", layout, key=TAB_URLS)


def create_hashtag_tab() -> FreeSimpleGUI.Tab:
    """Create the Hashtag scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for hashtag scraping.

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
        [
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}hashtag",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Hashtag", layout, key=TAB_HASHTAG)


def create_location_tab() -> FreeSimpleGUI.Tab:
    """Create the Location scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for location scraping.

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
        [
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}location",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Location", layout, key=TAB_LOCATION)


def create_followers_tab() -> FreeSimpleGUI.Tab:
    """Create the Followers scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for followers discovery.

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
        [
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}followers",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Followers", layout, key=TAB_FOLLOWERS)


def create_following_tab() -> FreeSimpleGUI.Tab:
    """Create the Following scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for following discovery.

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
        [
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}following",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Following", layout, key=TAB_FOLLOWING)


def create_likers_tab() -> FreeSimpleGUI.Tab:
    """Create the Likers scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for likers discovery.

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
        [
            FreeSimpleGUI.Push(),
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}likers",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Likers", layout, key=TAB_LIKERS)


def create_commenters_tab() -> FreeSimpleGUI.Tab:
    """Create the Commenters scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for commenters discovery.

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
            FreeSimpleGUI.Button(
                "Start Scrape",
                key=f"{EVENT_START_SCRAPE}commenters",
                button_color=("white", "#2E7D32"),
                size=(15, 1),
            ),
        ],
    ]
    return FreeSimpleGUI.Tab("Commenters", layout, key=TAB_COMMENTERS)


def create_stories_tab() -> FreeSimpleGUI.Tab:
    """Create the Stories scrape tab.

    Returns
    -------
    sg.Tab
        Tab element for stories scraping.

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
            [
                FreeSimpleGUI.Push(),
                FreeSimpleGUI.Button(
                    "Start Scrape",
                    key=f"{EVENT_START_SCRAPE}stories",
                    button_color=("white", "#2E7D32"),
                    size=(15, 1),
                ),
            ],
        ],
        key=TAB_STORIES,
    )


def create_main_window() -> FreeSimpleGUI.Window:
    """Create and return the main application window.

    Returns
    -------
    sg.Window
        The main application window.

    """
    # Create tab group with all scrape modes
    tab_group = FreeSimpleGUI.TabGroup(
        [
            [
                create_profile_tab(),
                create_url_tab(),
                create_urls_tab(),
                create_hashtag_tab(),
                create_location_tab(),
            ],
            [
                create_followers_tab(),
                create_following_tab(),
                create_likers_tab(),
                create_commenters_tab(),
                create_stories_tab(),
            ],
        ],
        key="-TAB-GROUP-",
        enable_events=True,
    )

    # Main layout
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
        # Progress and status section
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
                key=EVENT_STOP_SCRAPE,
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
        # Log output section
        [
            FreeSimpleGUI.Text("Log Output:", font=("Helvetica", 10, "bold")),
        ],
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
            FreeSimpleGUI.Button("Exit", key=EVENT_EXIT),
        ],
    ]

    return FreeSimpleGUI.Window(
        "Instagram Scraper GUI",
        layout,
        resizable=True,
        finalize=True,
        size=(900, 800),
    )


def get_shared_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Extract shared settings from form values.

    Returns
    -------
    dict[str, Any]
        Dictionary of shared settings.

    """
    settings: dict[str, Any] = {}

    output_dir = values.get("-OUTPUT-DIR-", "data")
    if output_dir:
        settings["output_dir"] = Path(output_dir)

    cookie_header = values.get("-COOKIE-HEADER-", "")
    settings["cookie_header"] = cookie_header
    settings["has_auth"] = bool(cookie_header)

    if limit_str := values.get("-LIMIT-", "").strip():
        with contextlib.suppress(ValueError):
            settings["limit"] = int(limit_str)

    timeout_str = values.get("-REQUEST-TIMEOUT-", "30").strip()
    with contextlib.suppress(ValueError):
        settings["request_timeout"] = int(timeout_str)
    if "request_timeout" not in settings:
        settings["request_timeout"] = 30

    retries_str = values.get("-MAX-RETRIES-", "5").strip()
    with contextlib.suppress(ValueError):
        settings["max_retries"] = int(retries_str)
    if "max_retries" not in settings:
        settings["max_retries"] = 5

    checkpoint_str = values.get("-CHECKPOINT-EVERY-", "20").strip()
    with contextlib.suppress(ValueError):
        settings["checkpoint_every"] = int(checkpoint_str)
    if "checkpoint_every" not in settings:
        settings["checkpoint_every"] = 20

    settings["raw_captures"] = bool(values.get("-RAW-CAPTURES-"))

    min_delay_str = values.get("-MIN-DELAY-", "0.05").strip()
    with contextlib.suppress(ValueError):
        settings["min_delay"] = float(min_delay_str)
    if "min_delay" not in settings:
        settings["min_delay"] = 0.05

    max_delay_str = values.get("-MAX-DELAY-", "0.2").strip()
    with contextlib.suppress(ValueError):
        settings["max_delay"] = float(max_delay_str)
    if "max_delay" not in settings:
        settings["max_delay"] = 0.2

    return settings


def _extract_int(values: dict[str, Any], key: str, default: int) -> int:
    """Extract an integer from values dictionary.

    Returns
    -------
    int
        The extracted integer.

    """
    val_str = values.get(key, str(default)).strip()
    with contextlib.suppress(ValueError):
        return int(val_str) if val_str else default
    return default


def _extract_float(values: dict[str, Any], key: str, default: float) -> float:
    """Extract a float from values dictionary.

    Returns
    -------
    float
        The extracted float.

    """
    val_str = values.get(key, str(default)).strip()
    with contextlib.suppress(ValueError):
        return float(val_str) if val_str else default
    return default


def build_scraper_config(values: dict[str, Any]) -> ScraperConfig:
    """Build a ScraperConfig from GUI form values.

    Parameters
    ----------
    values : dict[str, Any]
        Form values from the GUI.

    Returns
    -------
    ScraperConfig
        The built configuration object.

    """
    output_dir = Path(values.get("-OUTPUT-DIR-", "data") or "data")

    limit_val = values.get("-LIMIT-", "").strip()
    limit = int(limit_val) if limit_val and limit_val.isdigit() else None

    http_config = HttpConfig(
        timeout=_extract_int(values, "-REQUEST-TIMEOUT-", 30),
        max_retries=_extract_int(values, "-MAX-RETRIES-", 5),
        min_delay=_extract_float(values, "-MIN-DELAY-", 0.05),
        max_delay=_extract_float(values, "-MAX-DELAY-", 0.2),
        cookie_header=values.get("-COOKIE-HEADER-", ""),
    )

    output_config = OutputConfig(
        output_dir=output_dir,
        should_reset_output=bool(values.get("-URLS-RESET-OUTPUT-")),
        checkpoint_every=_extract_int(values, "-CHECKPOINT-EVERY-", 20),
    )

    return ScraperConfig(
        http=http_config,
        output=output_config,
        should_resume=bool(values.get("-URLS-RESUME-")),
        limit=limit,
    )


def _get_required_input(
    values: dict[str, Any],
    key: str,
    error_msg: str,
) -> str | None:
    """Get a required input value and show error if empty.

    Returns
    -------
    str | None
        The input value if present, None if empty.

    """
    value = values.get(key, "").strip()
    if not value:
        FreeSimpleGUI.popup_error(error_msg)
        return None
    return value


def _add_posts_limit(
    kwargs: dict[str, Any],
    values: dict[str, Any],
    key: str,
) -> None:
    """Add posts_limit to kwargs if provided."""
    if posts_limit_str := values.get(key, "").strip():
        with contextlib.suppress(ValueError):
            kwargs["posts_limit"] = int(posts_limit_str)


def _configure_profile_mode(
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for profile scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    username = _get_required_input(
        values,
        "-PROFILE-USERNAME-",
        "Username is required for profile scraping.",
    )
    if username is None:
        return None
    kwargs["username"] = username
    return kwargs


def _configure_url_mode(
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for single URL scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    post_url = _get_required_input(
        values,
        "-URL-POST_URL-",
        "Post URL is required.",
    )
    if post_url is None:
        return None
    kwargs["post_url"] = post_url
    return kwargs


def _configure_urls_mode(
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for multiple URLs scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    input_path = _get_required_input(
        values,
        "-URLS-INPUT-",
        "Input file is required.",
    )
    if input_path is None:
        return None
    kwargs["input_path"] = Path(input_path)
    kwargs["resume"] = values.get("-URLS-RESUME-", False)
    kwargs["reset_output"] = values.get("-URLS-RESET-OUTPUT-", False)
    return kwargs


def _configure_hashtag_mode(
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for hashtag scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    hashtag = _get_required_input(
        values,
        "-HASHTAG-HASHTAG-",
        "Hashtag is required.",
    )
    if hashtag is None:
        return None
    kwargs["hashtag"] = hashtag
    return kwargs


def _configure_location_mode(
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for location scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    location = _get_required_input(
        values,
        "-LOCATION-LOCATION-",
        "Location is required.",
    )
    if location is None:
        return None
    kwargs["location"] = location
    return kwargs


def _configure_follow_mode(
    mode: str,
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for followers or following scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    username_key = f"-{mode.upper()}-USERNAME-"
    username = _get_required_input(
        values,
        username_key,
        f"Username is required for {mode} scraping.",
    )
    if username is None:
        return None
    kwargs["username"] = username
    return kwargs


def _configure_likers_mode(
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for likers scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    username = _get_required_input(
        values,
        "-LIKERS-USERNAME-",
        "Username is required for likers scraping.",
    )
    if username is None:
        return None
    kwargs["username"] = username
    _add_posts_limit(kwargs, values, "-LIKERS-POSTS-LIMIT-")
    return kwargs


def _configure_commenters_mode(
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for commenters scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    username = _get_required_input(
        values,
        "-COMMENTERS-USERNAME-",
        "Username is required for commenters scraping.",
    )
    if username is None:
        return None
    kwargs["username"] = username
    _add_posts_limit(kwargs, values, "-COMMENTERS-POSTS-LIMIT-")
    return kwargs


def _configure_stories_mode(
    kwargs: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Configure kwargs for stories scraping mode.

    Returns
    -------
    dict[str, Any] | None
        Updated kwargs or None if validation failed.

    """
    if use_username := values.get("-STORIES-MODE-USERNAME-", True):
        value = _get_required_input(
            values,
            "-STORIES-USERNAME-",
            "Username is required for stories scraping.",
        )
    else:
        value = _get_required_input(
            values,
            "-STORIES-HASHTAG-",
            "Hashtag is required for stories scraping.",
        )

    if value is None:
        return None
    kwargs["username"] = value if use_username else None
    kwargs["hashtag"] = None if use_username else value
    return kwargs


def build_scrape_kwargs(
    mode: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """Build kwargs for the specified scrape mode from form values.

    Parameters
    ----------
    mode : str
        The scrape mode to configure.
    values : dict[str, Any]
        Form values from the GUI.

    Returns
    -------
    dict[str, Any] | None
        Configured kwargs or None if validation failed.

    """
    kwargs = get_shared_settings(values)

    mode_configs: dict[str, Callable[[dict, dict], dict | None]] = {
        "profile": _configure_profile_mode,
        "url": _configure_url_mode,
        "urls": _configure_urls_mode,
        "hashtag": _configure_hashtag_mode,
        "location": _configure_location_mode,
        "followers": lambda k, v: _configure_follow_mode("followers", k, v),
        "following": lambda k, v: _configure_follow_mode("following", k, v),
        "likers": _configure_likers_mode,
        "commenters": _configure_commenters_mode,
        "stories": _configure_stories_mode,
    }

    config_func = mode_configs.get(mode)
    if config_func is None:
        FreeSimpleGUI.popup_error(f"Unknown scrape mode: {mode}")
        return None

    return config_func(kwargs, values)


def update_ui_for_scrape_start(window: FreeSimpleGUI.Window) -> None:
    """Update UI elements when a scrape starts."""
    window["-STATUS-TEXT-"].update("Running...", text_color="orange")
    window[EVENT_STOP_SCRAPE].update(disabled=False)
    window["-PROGRESS-BAR-"].update_bar(0, 100)

    # Disable all start buttons
    for mode in [
        "profile",
        "url",
        "urls",
        "hashtag",
        "location",
        "followers",
        "following",
        "likers",
        "commenters",
        "stories",
    ]:
        window[f"{EVENT_START_SCRAPE}{mode}"].update(disabled=True)


def update_ui_for_scrape_end(
    window: FreeSimpleGUI.Window,
    *,
    success: bool = True,
) -> None:
    """Update UI elements when a scrape ends."""
    status_text = "Complete" if success else "Failed"
    status_color = "green" if success else "red"
    window["-STATUS-TEXT-"].update(status_text, text_color=status_color)
    window[EVENT_STOP_SCRAPE].update(disabled=True)

    # Re-enable all start buttons
    for mode in [
        "profile",
        "url",
        "urls",
        "hashtag",
        "location",
        "followers",
        "following",
        "likers",
        "commenters",
        "stories",
    ]:
        window[f"{EVENT_START_SCRAPE}{mode}"].update(disabled=False)


# Constants
PROGRESS_TUPLE_LEN = 2


def _handle_scrape_complete(
    window: FreeSimpleGUI.Window,
    result: dict[str, Any],
) -> None:
    """Handle scrape completion event."""
    if result["success"]:
        summary = result.get("summary", {})
        print("\nScrape completed successfully!")  # noqa: T201
        print(f"Users: {summary.get('users', 0)}")  # noqa: T201
        print(f"Posts: {summary.get('posts', 0)}")  # noqa: T201
        print(f"Comments: {summary.get('comments', 0)}")  # noqa: T201
        print(f"Stories: {summary.get('stories', 0)}")  # noqa: T201
        print(f"Errors: {summary.get('errors', 0)}")  # noqa: T201
        print(f"Output: {summary.get('output_dir', 'N/A')}")  # noqa: T201
    update_ui_for_scrape_end(window, success=True)


def _handle_scrape_error(
    window: FreeSimpleGUI.Window,
    result: dict[str, Any],
) -> None:
    """Handle scrape error event."""
    error_type = result.get("error_type", "unknown")
    if result.get("cancelled"):
        print("\nScrape cancelled by user.")  # noqa: T201
    else:
        print("\nScrape failed!")  # noqa: T201
        print(f"Error: {result['error']}")  # noqa: T201
        if error_type == "authentication":
            print("Hint: Check your cookie header and try again.")  # noqa: T201
        elif error_type == "rate_limit" and result.get("retry_after"):
            print(f"Retry after: {result['retry_after']} seconds")  # noqa: T201
    if result.get("detail"):
        print(f"Details: {result['detail']}")  # noqa: T201
    update_ui_for_scrape_end(window, success=False)


def _handle_progress_update(
    window: FreeSimpleGUI.Window,
    values: dict[str, Any],
) -> None:
    progress_data = values.get(EVENT_PROGRESS_UPDATE)
    if isinstance(progress_data, tuple) and len(progress_data) == PROGRESS_TUPLE_LEN:
        current, total = progress_data
        window["-PROGRESS-BAR-"].update_bar(current, total)  # type: ignore[attr-defined]


def _validate_auth_for_mode(mode: str, values: dict[str, Any]) -> bool:
    if mode in AUTH_REQUIRED_MODES:
        cookie_header = values.get("-COOKIE-HEADER-", "").strip()
        if not cookie_header:
            descriptor = describe_mode_capability(mode)
            FreeSimpleGUI.popup_error(
                f"'{mode}' mode requires authentication.\n\n"
                f"Please provide a Cookie Header in the Shared Settings section.\n"
                f"Support tier: {descriptor.support_tier}",
                title="Authentication Required",
            )
            return False
    return True


def _process_start_scrape(
    window: FreeSimpleGUI.Window,
    worker: ScraperWorker,
    event: str,
    values: dict[str, Any],
) -> None:
    """Handle start scrape button click."""
    if not isinstance(event, str):
        return
    if not event.startswith(EVENT_START_SCRAPE):
        return
    mode = event.replace(EVENT_START_SCRAPE, "")
    if not _validate_auth_for_mode(mode, values):
        return

    kwargs = build_scrape_kwargs(mode, values)
    if kwargs is not None:
        update_ui_for_scrape_start(window)
        print(f"\nStarting {mode} scrape...")  # noqa: T201
        worker.start_scrape(mode, kwargs)


def _handle_scrape_events(
    window: FreeSimpleGUI.Window,
    event: str,
    values: dict[str, Any],
) -> None:
    """Handle scrape-related events."""
    if event == EVENT_SCRAPE_COMPLETE:
        _handle_scrape_complete(window, values[event])
    elif event == EVENT_SCRAPE_ERROR:
        _handle_scrape_error(window, values[event])
    elif event == EVENT_PROGRESS_UPDATE:
        _handle_progress_update(window, values)


def _handle_ui_events(
    window: FreeSimpleGUI.Window,
    event: str,
    values: dict[str, Any],
) -> None:
    """Handle UI-related events."""
    match event:
        case "-SHOW-ADVANCED-":
            window["-ADVANCED-SETTINGS-COL-"].update(
                visible=values.get("-SHOW-ADVANCED-", False),
            )  # type: ignore[attr-defined]
        case "-TOGGLE-COOKIE-":
            current = window["-COOKIE-HEADER-"]
            is_masked = current.PasswordCharacter == "*"
            current.update(password_char="" if is_masked else "*")
            window["-TOGGLE-COOKIE-"].update("Hide" if is_masked else "Show")
        case "-STORIES-MODE-USERNAME-":
            window["-STORIES-USERNAME-COL-"].update(visible=True)
            window["-STORIES-HASHTAG-COL-"].update(visible=False)
        case "-STORIES-MODE-HASHTAG-":
            window["-STORIES-USERNAME-COL-"].update(visible=False)
            window["-STORIES-HASHTAG-COL-"].update(visible=True)


def _process_event(
    window: FreeSimpleGUI.Window,
    worker: ScraperWorker,
    event: str,
    values: dict[str, Any],
) -> bool:
    """Process a single GUI event.

    Returns
    -------
    bool
        False if the main loop should exit, True otherwise.

    """
    if event in {FreeSimpleGUI.WIN_CLOSED, EVENT_EXIT}:
        if worker.is_running():
            worker.request_stop()
        return False

    if event == "-CLEAR-LOG-":
        window["-LOG-OUTPUT-"].update("")
    elif isinstance(event, str) and event.startswith(EVENT_START_SCRAPE):
        _process_start_scrape(window, worker, event, values)
    elif event == EVENT_STOP_SCRAPE:
        worker.request_stop()
        print("Stop requested. Waiting...")  # noqa: T201
        window["-STATUS-TEXT-"].update("Stopping...", text_color="orange")
    elif event in {EVENT_SCRAPE_COMPLETE, EVENT_SCRAPE_ERROR, EVENT_PROGRESS_UPDATE}:
        _handle_scrape_events(window, event, values)
    else:
        _handle_ui_events(window, event, values)

    return True


def run_gui() -> None:
    """Run the main GUI application loop."""
    window = create_main_window()
    worker = ScraperWorker(window)

    logger.info("Instagram Scraper GUI initialized")
    print("Instagram Scraper GUI initialized.")  # noqa: T201
    print("Select a scrape mode and enter required parameters.")  # noqa: T201
    print("Note: Some modes require authentication via Cookie Header.")  # noqa: T201
    print("-" * 60)  # noqa: T201

    running = True
    while running:
        event, values = window.read(timeout=100)
        running = _process_event(window, worker, event, values)

    window.close()


def main() -> None:
    """CLI entry point for the GUI."""
    run_gui()


if __name__ == "__main__":
    main()
