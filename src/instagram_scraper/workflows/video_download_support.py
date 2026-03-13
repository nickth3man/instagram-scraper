# Copyright (c) 2026
"""Support helpers for scalable video download workflows."""

from __future__ import annotations

import csv
import json
import sqlite3
import threading
from typing import TYPE_CHECKING, cast

from instagram_scraper.infrastructure.instagram_http import build_instagram_session

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    import requests

MEDIA_TYPE_VIDEO = "2"
MEDIA_TYPE_CAROUSEL = "8"
COMMENTS_INDEX_TABLE = "video_comments"
CREATE_COMMENTS_TABLE_SQL = (
    "CREATE TABLE video_comments ("
    "row_id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "shortcode TEXT NOT NULL, "
    "payload TEXT NOT NULL"
    ")"
)
CREATE_COMMENTS_INDEX_SQL = (
    "CREATE INDEX idx_video_comments_shortcode ON video_comments(shortcode)"
)
SELECT_COMMENTS_SQL = (
    "SELECT payload FROM video_comments WHERE shortcode = ? ORDER BY row_id"
)
INSERT_COMMENT_SQL = "INSERT INTO video_comments (shortcode, payload) VALUES (?, ?)"
COMMENT_BATCH_SIZE = 500


class CommentsLookup:
    """Disk-backed lookup for comments grouped by shortcode.

    The lookup streams `comments.csv` into a temporary SQLite index so large
    comment datasets do not need to be retained in memory.
    """

    def __init__(self, comments_csv_path: Path, index_path: Path) -> None:
        self._comments_csv_path = comments_csv_path
        self._index_path = index_path
        self._connection: sqlite3.Connection | None = None
        self._initialized = False

    def get(self, shortcode: str) -> list[dict[str, str]]:
        """Return comments for the provided shortcode.

        Returns
        -------
        list[dict[str, str]]
            Comment rows associated with the requested shortcode.

        """
        if not shortcode:
            return []
        connection = self._ensure_connection()
        cursor = connection.execute(SELECT_COMMENTS_SQL, (shortcode,))
        return [cast("dict[str, str]", json.loads(payload)) for (payload,) in cursor]

    def close(self) -> None:
        """Close the index connection and remove the temporary database."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        self._index_path.unlink(missing_ok=True)

    def _ensure_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
            self._index_path.unlink(missing_ok=True)
            self._connection = sqlite3.connect(self._index_path)
            self._initialize(self._connection)
        return self._connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        if self._initialized:
            return
        connection.execute(CREATE_COMMENTS_TABLE_SQL)
        connection.execute(CREATE_COMMENTS_INDEX_SQL)
        if self._comments_csv_path.exists():
            with self._comments_csv_path.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as file:
                reader = csv.DictReader(file)
                rows: list[tuple[str, str]] = []
                for row in reader:
                    shortcode = row.get("post_shortcode") or row.get("shortcode")
                    if not shortcode:
                        continue
                    rows.append((shortcode, json.dumps(dict(row), ensure_ascii=False)))
                    if len(rows) >= COMMENT_BATCH_SIZE:
                        connection.executemany(INSERT_COMMENT_SQL, rows)
                        rows.clear()
                if rows:
                    connection.executemany(INSERT_COMMENT_SQL, rows)
        connection.commit()
        self._initialized = True


class DownloadSessionPool:
    """Thread-local `requests.Session` pool for concurrent downloads."""

    def __init__(self, cookie_header: str) -> None:
        self._cookie_header = cookie_header
        self._local = threading.local()
        self._sessions: list[requests.Session] = []
        self._lock = threading.Lock()

    def get(self) -> requests.Session:
        """Return the session bound to the current thread.

        Returns
        -------
        requests.Session
            A thread-local session configured for Instagram downloads.

        """
        session = getattr(self._local, "session", None)
        if session is not None:
            return cast("requests.Session", session)
        created = build_instagram_session(self._cookie_header)
        self._local.session = created
        with self._lock:
            self._sessions.append(created)
        return created

    def close(self) -> None:
        """Close all sessions created by the pool."""
        with self._lock:
            sessions = list(self._sessions)
            self._sessions.clear()
        for session in sessions:
            session.close()


def iter_target_rows(posts_csv: Path, limit: int | None) -> Iterator[dict[str, str]]:
    """Stream downloadable target rows without materializing the whole CSV.

    Rows are yielded in two passes so plain video posts are handled before
    carousels while keeping memory usage bounded.

    Yields
    ------
    dict[str, str]
        Matching video or carousel rows in download order.

    """
    yielded = 0
    for media_type in (MEDIA_TYPE_VIDEO, MEDIA_TYPE_CAROUSEL):
        with posts_csv.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if limit is not None and yielded >= limit:
                    return
                if row.get("type") != media_type:
                    continue
                yield dict(row)
                yielded += 1
