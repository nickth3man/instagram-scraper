# Copyright (c) 2026
"""Desktop GUI for Instagram Scraper using FreeSimpleGUI."""

from __future__ import annotations

import contextlib
import threading
import traceback
from pathlib import Path
from typing import Any, Protocol, cast

import FreeSimpleGUI

from instagram_scraper.config import HttpConfig, OutputConfig, ScraperConfig
from instagram_scraper.core.capabilities import (
    AUTH_REQUIRED_MODES,
    describe_mode_capability,
)
from instagram_scraper.core.mode_registry import (
    ModeInputError,
    get_scrape_mode_definition,
)
from instagram_scraper.core.pipeline import PipelineCancelledError, execute_pipeline
from instagram_scraper.exceptions import (
    AuthenticationError,
    InstagramError,
    NetworkError,
    RateLimitError,
)
from instagram_scraper.infrastructure.logging import get_logger
from instagram_scraper.ui import layout as gui_layout

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


class _ElementWithUpdate(Protocol):
    def update(self, value: object | None = None, **kwargs: object) -> object: ...


class _ProgressBarElement(Protocol):
    def update_bar(
        self,
        current_count: int,
        maximum: int | None = None,
    ) -> object: ...


class _PasswordInputElement(_ElementWithUpdate, Protocol):
    PasswordCharacter: str | None


def _element(window: FreeSimpleGUI.Window, key: str) -> _ElementWithUpdate:
    return cast("_ElementWithUpdate", window[key])


def _progress_bar(window: FreeSimpleGUI.Window) -> _ProgressBarElement:
    return cast("_ProgressBarElement", window["-PROGRESS-BAR-"])


def _password_input(window: FreeSimpleGUI.Window) -> _PasswordInputElement:
    return cast("_PasswordInputElement", window["-COOKIE-HEADER-"])


def _append_log(window: FreeSimpleGUI.Window, message: str) -> None:
    _element(window, "-LOG-OUTPUT-").update(f"{message}\n", append=True)


def _set_status(window: FreeSimpleGUI.Window, text: str, *, color: str) -> None:
    _element(window, "-STATUS-TEXT-").update(text, text_color=color)


class ScraperWorker:
    """Run scrapes in a background thread."""

    def __init__(self, window: FreeSimpleGUI.Window) -> None:
        self.window = window
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start_scrape(self, mode: str, kwargs: dict[str, Any]) -> None:
        """Start a scrape in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._scrape_thread,
            args=(mode, kwargs),
            daemon=True,
        )
        self._thread.start()

    def _scrape_thread(self, mode: str, kwargs: dict[str, Any]) -> None:
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
        except (LookupError, OSError, RuntimeError, TypeError, ValueError) as exc:
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
        """Return whether the worker thread is active.

        Returns
        -------
        bool: True when the background thread is still running.
        """
        return self._thread is not None and self._thread.is_alive()

    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """Wait for the worker thread to complete.

        Returns
        -------
        bool: True when the worker has finished before the timeout.
        """
        if self._thread is None:
            return True
        self._thread.join(timeout)
        return not self._thread.is_alive()


def create_main_window() -> FreeSimpleGUI.Window:
    """Create the main application window.

    Returns
    -------
    FreeSimpleGUI.Window: Configured desktop window for the GUI loop.
    """
    return gui_layout.create_main_window(
        start_event_prefix=EVENT_START_SCRAPE,
        stop_event_key=EVENT_STOP_SCRAPE,
        exit_event_key=EVENT_EXIT,
    )


def get_shared_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Extract shared settings from GUI form values.

    Returns
    -------
    dict[str, Any]: Shared scrape settings derived from the current form values.
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
    val_str = values.get(key, str(default)).strip()
    with contextlib.suppress(ValueError):
        return int(val_str) if val_str else default
    return default


def _extract_float(values: dict[str, Any], key: str, default: float) -> float:
    val_str = values.get(key, str(default)).strip()
    with contextlib.suppress(ValueError):
        return float(val_str) if val_str else default
    return default


def build_scraper_config(values: dict[str, Any]) -> ScraperConfig:
    """Build a `ScraperConfig` from GUI form values.

    Returns
    -------
    ScraperConfig: Normalized scraper configuration for the GUI submission.
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


def build_scrape_kwargs(mode: str, values: dict[str, Any]) -> dict[str, Any] | None:
    """Build scrape kwargs from shared and mode-specific settings.

    Returns
    -------
    dict[str, Any] | None: Mode-ready kwargs, or `None` when validation fails.
    """
    kwargs = get_shared_settings(values)

    try:
        mode_kwargs = get_scrape_mode_definition(mode).gui_builder(values)
    except ModeInputError as exc:
        FreeSimpleGUI.popup_error(str(exc))
        return None
    except ValueError:
        FreeSimpleGUI.popup_error(f"Unknown scrape mode: {mode}")
        return None

    kwargs.update(mode_kwargs)
    return kwargs


def update_ui_for_scrape_start(window: FreeSimpleGUI.Window) -> None:
    """Update UI elements when a scrape starts."""
    _set_status(window, "Running...", color="orange")
    _element(window, EVENT_STOP_SCRAPE).update(disabled=False)
    _progress_bar(window).update_bar(0, 100)

    for mode in gui_layout.SCRAPE_MODES:
        _element(window, f"{EVENT_START_SCRAPE}{mode}").update(disabled=True)


def update_ui_for_scrape_end(
    window: FreeSimpleGUI.Window,
    *,
    success: bool = True,
) -> None:
    """Update UI elements when a scrape ends."""
    status_text = "Complete" if success else "Failed"
    status_color = "green" if success else "red"
    _set_status(window, status_text, color=status_color)
    _element(window, EVENT_STOP_SCRAPE).update(disabled=True)

    for mode in gui_layout.SCRAPE_MODES:
        _element(window, f"{EVENT_START_SCRAPE}{mode}").update(disabled=False)


PROGRESS_TUPLE_LEN = 2


def _handle_scrape_complete(
    window: FreeSimpleGUI.Window,
    result: dict[str, Any],
) -> None:
    if result["success"]:
        summary = result.get("summary", {})
        _append_log(window, "")
        _append_log(window, "Scrape completed successfully!")
        _append_log(window, f"Users: {summary.get('users', 0)}")
        _append_log(window, f"Posts: {summary.get('posts', 0)}")
        _append_log(window, f"Comments: {summary.get('comments', 0)}")
        _append_log(window, f"Stories: {summary.get('stories', 0)}")
        _append_log(window, f"Errors: {summary.get('errors', 0)}")
        _append_log(window, f"Output: {summary.get('output_dir', 'N/A')}")
    update_ui_for_scrape_end(window, success=True)


def _handle_scrape_error(
    window: FreeSimpleGUI.Window,
    result: dict[str, Any],
) -> None:
    error_type = result.get("error_type", "unknown")
    if result.get("cancelled"):
        _append_log(window, "")
        _append_log(window, "Scrape cancelled by user.")
    else:
        _append_log(window, "")
        _append_log(window, "Scrape failed!")
        _append_log(window, f"Error: {result['error']}")
        if error_type == "authentication":
            _append_log(window, "Hint: Check your cookie header and try again.")
        elif error_type == "rate_limit" and result.get("retry_after"):
            _append_log(window, f"Retry after: {result['retry_after']} seconds")
    if result.get("detail"):
        _append_log(window, f"Details: {result['detail']}")
    update_ui_for_scrape_end(window, success=False)


def _handle_progress_update(
    window: FreeSimpleGUI.Window,
    values: dict[str, Any],
) -> None:
    progress_data = values.get(EVENT_PROGRESS_UPDATE)
    if isinstance(progress_data, tuple) and len(progress_data) == PROGRESS_TUPLE_LEN:
        current, total = progress_data
        _progress_bar(window).update_bar(current, total)


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
    event: object,
    values: dict[str, Any],
) -> None:
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
        _append_log(window, "")
        _append_log(window, f"Starting {mode} scrape...")
        worker.start_scrape(mode, kwargs)


def _handle_scrape_events(
    window: FreeSimpleGUI.Window,
    event: object,
    values: dict[str, Any],
) -> None:
    if event == EVENT_SCRAPE_COMPLETE:
        _handle_scrape_complete(window, values[EVENT_SCRAPE_COMPLETE])
    elif event == EVENT_SCRAPE_ERROR:
        _handle_scrape_error(window, values[EVENT_SCRAPE_ERROR])
    elif event == EVENT_PROGRESS_UPDATE:
        _handle_progress_update(window, values)


def _handle_ui_events(
    window: FreeSimpleGUI.Window,
    event: object,
    values: dict[str, Any],
) -> None:
    match event:
        case "-SHOW-ADVANCED-":
            _element(window, "-ADVANCED-SETTINGS-COL-").update(
                visible=values.get("-SHOW-ADVANCED-", False),
            )
        case "-TOGGLE-COOKIE-":
            current = _password_input(window)
            is_masked = current.PasswordCharacter == "*"
            current.update(password_char="" if is_masked else "*")
            _element(window, "-TOGGLE-COOKIE-").update(
                "Hide" if is_masked else "Show",
            )
        case "-STORIES-MODE-USERNAME-":
            _element(window, "-STORIES-USERNAME-COL-").update(visible=True)
            _element(window, "-STORIES-HASHTAG-COL-").update(visible=False)
        case "-STORIES-MODE-HASHTAG-":
            _element(window, "-STORIES-USERNAME-COL-").update(visible=False)
            _element(window, "-STORIES-HASHTAG-COL-").update(visible=True)


def _process_event(
    window: FreeSimpleGUI.Window,
    worker: ScraperWorker,
    event: object,
    values: dict[str, Any],
) -> bool:
    if event in {FreeSimpleGUI.WIN_CLOSED, EVENT_EXIT}:
        if worker.is_running():
            worker.request_stop()
        return False

    if event == "-CLEAR-LOG-":
        _element(window, "-LOG-OUTPUT-").update("")
    elif isinstance(event, str) and event.startswith(EVENT_START_SCRAPE):
        _process_start_scrape(window, worker, event, values)
    elif event == EVENT_STOP_SCRAPE:
        worker.request_stop()
        _append_log(window, "Stop requested. Waiting...")
        _set_status(window, "Stopping...", color="orange")
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
    _append_log(window, "Instagram Scraper GUI initialized.")
    _append_log(window, "Select a scrape mode and enter required parameters.")
    _append_log(window, "Note: Some modes require authentication via Cookie Header.")
    _append_log(window, "-" * 60)

    running = True
    while running:
        read_result = window.read(timeout=100)
        if not isinstance(read_result, tuple) or len(read_result) != PROGRESS_TUPLE_LEN:
            event, values = FreeSimpleGUI.WIN_CLOSED, {}
        else:
            event, values = read_result
        current_values = values if isinstance(values, dict) else {}
        running = _process_event(window, worker, event, current_values)

    window.close()


def main() -> None:
    """CLI entry point for the GUI."""
    run_gui()


if __name__ == "__main__":
    main()
