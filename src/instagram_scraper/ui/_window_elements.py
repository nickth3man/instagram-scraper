# Copyright (c) 2026
"""Window element access helpers for the desktop GUI."""

from __future__ import annotations

from typing import Any, Protocol, cast

Window = Any


class ElementWithUpdate(Protocol):
    """Protocol for GUI elements supporting ``update``."""

    def update(self, value: object | None = None, **kwargs: object) -> object: ...


class ProgressBarElement(Protocol):
    """Protocol for GUI progress-bar elements."""

    def update_bar(
        self,
        current_count: int,
        maximum: int | None = None,
    ) -> object: ...


class PasswordInputElement(ElementWithUpdate, Protocol):
    """Protocol for password input widgets with masking state."""

    PasswordCharacter: str | None


def element(window: Window, key: str) -> ElementWithUpdate:
    """Return a typed element handle from the GUI window.

    Returns
    -------
        Element wrapper supporting ``update``.
    """
    return cast("ElementWithUpdate", window[key])


def progress_bar(window: Window) -> ProgressBarElement:
    """Return the progress-bar widget from the GUI window.

    Returns
    -------
        Progress bar element wrapper.
    """
    return cast("ProgressBarElement", window["-PROGRESS-BAR-"])


def password_input(window: Window) -> PasswordInputElement:
    """Return the cookie-header input widget from the GUI window.

    Returns
    -------
        Password-capable input widget wrapper.
    """
    return cast("PasswordInputElement", window["-COOKIE-HEADER-"])


def append_log(window: Window, message: str) -> None:
    """Append one message to the GUI log output."""
    element(window, "-LOG-OUTPUT-").update(f"{message}\n", append=True)


def set_status(window: Window, text: str, *, color: str) -> None:
    """Update the GUI status label text and color."""
    element(window, "-STATUS-TEXT-").update(text, text_color=color)
