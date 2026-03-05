# Copyright (c) 2026
"""Disk-backed cache helpers for scraper runs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from diskcache import Cache

if TYPE_CHECKING:
    from pathlib import Path


class ScraperCache:
    """Small wrapper around a disk-backed cache namespace."""

    def __init__(self, directory: Path) -> None:
        """Open a cache rooted at the given directory."""
        self._cache = Cache(str(directory))

    def get(self, key: str) -> object | None:
        """Return a cached value when present.

        Returns
        -------
        object | None
            The cached value, or `None` when the key is absent.

        """
        return self._cache.get(key)

    def set(self, key: str, value: object) -> None:
        """Store a value in the cache."""
        self._cache.set(key, value)
