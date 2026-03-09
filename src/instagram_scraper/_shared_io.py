# Copyright (c) 2026
"""Shared filesystem helpers for scraper outputs and checkpoints."""

from __future__ import annotations

import csv
import json
import os
import time
from contextlib import contextmanager
from json import JSONDecodeError
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl as _fcntl


class _SyncFile(Protocol):
    """File-like protocol for flush and fsync durability helpers."""

    def flush(self) -> object: ...

    def fileno(self) -> int: ...


def _flush_and_fsync(file: _SyncFile) -> None:
    """Flush userspace buffers and force file contents to durable storage."""
    file.flush()
    os.fsync(file.fileno())


def _fsync_parent_directory(path: Path) -> None:
    """Best-effort metadata durability for file creates/replaces.

    Some platforms/filesystems do not allow opening directories for fsync, so
    failures are intentionally ignored after file content has already been made
    durable.
    """
    directory_fd: int | None = None
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(directory_fd)
    except OSError:
        return
    finally:
        if directory_fd is not None:
            os.close(directory_fd)


def _lock_path_for(path: Path) -> Path:
    """Return the sidecar lock file path used for inter-process coordination.

    Returns
    -------
    Path
        Lock sidecar path for ``path``.

    """
    return path.with_suffix(f"{path.suffix}.lock")


def _posix_flock(lock_file: _SyncFile, lock_name: str) -> None:
    """Apply a POSIX flock operation, raising a clear contract error if missing.

    Raises
    ------
    RuntimeError
        If ``fcntl.flock`` or the requested lock constant is unavailable.

    """
    flock = getattr(_fcntl, "flock", None)
    lock_flag = getattr(_fcntl, lock_name, None)
    if flock is None or lock_flag is None:
        msg = f"POSIX file locking requires fcntl.flock and fcntl.{lock_name}"
        raise RuntimeError(msg)
    flock(lock_file.fileno(), lock_flag)


@contextmanager
def locked_path(path: Path) -> Generator[None]:
    """Acquire an advisory inter-process lock for operations on ``path``.

    The lock is held on a sidecar file at ``<path>.lock`` for the entire
    context-manager scope. Any code path that mutates ``path`` should use this
    helper to serialize writers across processes.

    """
    # The `.lock` sidecar file lets two scraper runs coordinate access to the same
    # real output file without overwriting each other mid-write.
    lock_path = _lock_path_for(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                _flush_and_fsync(lock_file)
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            _posix_flock(lock_file, "LOCK_EX")
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                _posix_flock(lock_file, "LOCK_UN")


def atomic_write_text(path: Path, content: str) -> None:
    """Write text atomically with explicit best-effort durability semantics.

    The function writes to a temporary sibling file, fsyncs file contents,
    replaces the target atomically, then best-effort fsyncs the parent directory
    to reduce metadata-loss windows on abrupt crashes.
    """
    # Write into a temporary file first, then swap it into place in one step.
    # That way readers either see the old complete file or the new complete file.
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    with locked_path(path):
        try:
            with temp_path.open("w", encoding="utf-8") as file:
                file.write(content)
                _flush_and_fsync(file)
            temp_path.replace(path)
            _fsync_parent_directory(path)
        finally:
            temp_path.unlink(missing_ok=True)


def write_json_line(path: Path, payload: dict[str, object]) -> None:
    """Append one NDJSON row and fsync to make appended progress durable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(path), path.open("a", encoding="utf-8") as file:
        # NDJSON stores one JSON object per line, which makes large scrape outputs
        # easy to append to and stream later.
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        _flush_and_fsync(file)


def ensure_csv_with_header(path: Path, header: list[str], *, reset: bool) -> None:
    """Create a CSV file with a header row when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(path):
        if reset and path.exists():
            path.unlink()
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as file:
                # The header row names the columns so spreadsheet tools know how to
                # label each value in later rows.
                writer = csv.DictWriter(file, fieldnames=header)
                writer.writeheader()
                _flush_and_fsync(file)
                _fsync_parent_directory(path)


def append_csv_row(path: Path, header: list[str], row: dict[str, object]) -> None:
    """Append one CSV row and fsync to make appended progress durable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(path), path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=header)
        writer.writerow(row)
        _flush_and_fsync(file)


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
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError:
        return None
    return cast("dict[str, object]", payload) if isinstance(payload, dict) else None
