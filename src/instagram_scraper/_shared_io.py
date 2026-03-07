# Copyright (c) 2026
"""Shared filesystem helpers for scraper outputs and checkpoints."""

from __future__ import annotations

import csv
import json
import os
import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Generator

if os.name == "nt":
    import msvcrt
else:
    import fcntl


@contextmanager
def locked_path(path: Path) -> Generator[None]:
    """Acquire an inter-process file lock for the given path."""
    # The `.lock` sidecar file lets two scraper runs coordinate access to the same
    # real output file without overwriting each other mid-write.
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if os.name == "nt":
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write("\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            flock = fcntl.flock
            lock_ex = fcntl.LOCK_EX
            flock(lock_file.fileno(), lock_ex)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                flock = fcntl.flock
                lock_un = fcntl.LOCK_UN
                flock(lock_file.fileno(), lock_un)


def atomic_write_text(path: Path, content: str) -> None:
    """Write text atomically so readers never observe partial content."""
    # Write into a temporary file first, then swap it into place in one step.
    # That way readers either see the old complete file or the new complete file.
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    with locked_path(path):
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)


def write_json_line(path: Path, payload: dict[str, object]) -> None:
    """Append a single JSON document followed by a newline."""
    with locked_path(path), path.open("a", encoding="utf-8") as file:
        # NDJSON stores one JSON object per line, which makes large scrape outputs
        # easy to append to and stream later.
        file.write(_json_dumps(payload) + "\n")
        file.flush()
        os.fsync(file.fileno())


def ensure_csv_with_header(path: Path, header: list[str], *, reset: bool) -> None:
    """Create a CSV file with a header row when needed."""
    with locked_path(path):
        if reset and path.exists():
            path.unlink()
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as file:
                # The header row names the columns so spreadsheet tools know how to
                # label each value in later rows.
                writer = csv.DictWriter(file, fieldnames=header)
                writer.writeheader()
                file.flush()
                os.fsync(file.fileno())


def append_csv_row(path: Path, header: list[str], row: dict[str, object]) -> None:
    """Append a single row to a CSV file."""
    with locked_path(path), path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=header)
        writer.writerow(row)
        file.flush()
        os.fsync(file.fileno())


def load_json_dict(path: Path) -> dict[str, object] | None:
    """Load a JSON object from disk when the file exists.

    Returns
    -------
    dict[str, object] | None
        The decoded JSON object, or `None` when the file is missing.

    """
    if not path.exists():
        return None
    # Some helpers use `None` to mean "there is no saved state yet", so missing
    # files are treated as an expected case instead of an error.
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast("dict[str, object]", payload) if isinstance(payload, dict) else None


def _json_dumps(payload: dict[str, object]) -> str:
    """Serialize structured payloads with support for common path/date objects.

    Returns
    -------
    str
        The JSON-encoded payload string.

    """
    return json.dumps(payload, ensure_ascii=False, default=_json_default)


def _json_default(value: object) -> str:
    """Normalize non-JSON-native values for output files.

    Returns
    -------
    str
        A string representation suitable for JSON output.

    Raises
    ------
    TypeError
        Raised when the value cannot be normalized into JSON output.

    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    message = f"Object of type {type(value).__name__} is not JSON serializable"
    raise TypeError(message)
