# Copyright (c) 2026
"""Shared helpers for scrape-mode registry modules."""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from typing import Any

_ModeKwargs = dict[str, object]
_GuiValues = dict[str, Any]


class ModeInputError(ValueError):
    """Raised when GUI input for a scrape mode is invalid."""


def _load_attr(module_name: str, attr_name: str) -> object:
    module = import_module(module_name)
    return getattr(module, attr_name)


def _load_sync_attr(attr_name: str) -> object:
    return _load_attr("instagram_scraper.core.sync", attr_name)


def _required_str(kwargs: _ModeKwargs, key: str) -> str:
    value = kwargs.get(key)
    if isinstance(value, str):
        return value
    message = f"Expected string value for {key}"
    raise TypeError(message)


def _optional_str(kwargs: _ModeKwargs, key: str) -> str | None:
    value = kwargs.get(key)
    return value if isinstance(value, str) else None


def _optional_int(kwargs: _ModeKwargs, key: str) -> int | None:
    value = kwargs.get(key)
    return value if isinstance(value, int) else None


def _optional_float(kwargs: _ModeKwargs, key: str) -> float | None:
    value = kwargs.get(key)
    return value if isinstance(value, float) else None


def _optional_path(kwargs: _ModeKwargs, key: str) -> Path | None:
    value = kwargs.get(key)
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    message = f"Expected optional path-like value for {key}"
    raise TypeError(message)


def _path_arg(kwargs: _ModeKwargs, key: str) -> Path:
    value = kwargs.get(key)
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    message = f"Expected path-like value for {key}"
    raise TypeError(message)


def _required_text(values: _GuiValues, key: str, error_msg: str) -> str:
    raw_value = values.get(key, "")
    text = raw_value.strip() if isinstance(raw_value, str) else ""
    if text:
        return text
    raise ModeInputError(error_msg)


def _optional_text(values: _GuiValues, key: str) -> str | None:
    raw_value = values.get(key, "")
    if not isinstance(raw_value, str):
        return None
    text = raw_value.strip()
    return text or None


def _optional_gui_int(values: _GuiValues, key: str) -> int | None:
    raw_value = values.get(key, "")
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return None
        with suppress(ValueError):
            return int(text)
    return None
