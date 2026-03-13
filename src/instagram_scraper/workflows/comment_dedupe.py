# Copyright (c) 2026
"""Deterministic exact-row dedupe helpers for closure comment exports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from instagram_scraper.infrastructure.files import (
    append_csv_row,
    ensure_csv_with_header,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

COMMENT_ROW_FIELDNAMES = (
    "post_shortcode",
    "id",
    "parent_id",
    "created_at_utc",
    "text",
    "comment_like_count",
    "owner_username",
    "owner_id",
)


class _CommentRow(TypedDict):
    post_shortcode: str
    id: str
    parent_id: str
    created_at_utc: str
    text: str
    comment_like_count: str
    owner_username: str
    owner_id: str


@dataclass(frozen=True, slots=True)
class CommentDedupeSummary:
    """Audit output for deterministic exact-row comment dedupe.

    Attributes
    ----------
    total_rows:
        Count of comment rows before dedupe.
    unique_rows:
        Count of comment rows after exact-row dedupe.
    removed_rows:
        Count of duplicate rows removed.
    affected_shortcodes:
        Sorted shortcodes whose duplicate rows were removed.
    """

    total_rows: int
    unique_rows: int
    removed_rows: int
    affected_shortcodes: tuple[str, ...]


def comment_row_key(row: Mapping[str, object]) -> tuple[str, ...]:
    """Build the exact-row dedupe key for one closure comment row.

    Returns
    -------
    tuple[str, ...]
        Exact-row key ordered by the authoritative closure comment schema.
    """
    return tuple(str(row.get(field, "")) for field in COMMENT_ROW_FIELDNAMES)


def dedupe_comment_rows(
    rows: Iterable[Mapping[str, str]],
) -> tuple[list[_CommentRow], CommentDedupeSummary]:
    """Return first-seen exact rows and a deterministic dedupe summary.

    Returns
    -------
    tuple[list[dict[str, str]], CommentDedupeSummary]
        Unique rows in original order plus the dedupe audit summary.
    """
    unique_rows: list[_CommentRow] = []
    seen_keys: set[tuple[str, ...]] = set()
    duplicate_shortcodes: set[str] = set()
    total_rows = 0

    for row in rows:
        total_rows += 1
        normalized: _CommentRow = {
            "post_shortcode": row.get("post_shortcode", ""),
            "id": row.get("id", ""),
            "parent_id": row.get("parent_id", ""),
            "created_at_utc": row.get("created_at_utc", ""),
            "text": row.get("text", ""),
            "comment_like_count": row.get("comment_like_count", ""),
            "owner_username": row.get("owner_username", ""),
            "owner_id": row.get("owner_id", ""),
        }
        key = comment_row_key(normalized)
        if key in seen_keys:
            duplicate_shortcodes.add(normalized["post_shortcode"])
            continue
        seen_keys.add(key)
        unique_rows.append(normalized)

    summary = CommentDedupeSummary(
        total_rows=total_rows,
        unique_rows=len(unique_rows),
        removed_rows=total_rows - len(unique_rows),
        affected_shortcodes=tuple(sorted(duplicate_shortcodes)),
    )
    return unique_rows, summary


def audit_comment_csv(path: Path) -> CommentDedupeSummary:
    """Read a closure comment CSV and return deterministic dedupe counts.

    Returns
    -------
    CommentDedupeSummary
        Dedupe counts and affected shortcodes for the CSV.

    Raises
    ------
    ValueError
        The file header does not match the authoritative closure schema.
    """
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != COMMENT_ROW_FIELDNAMES:
            message = (
                "comments.csv must use the closure schema "
                f"{list(COMMENT_ROW_FIELDNAMES)}, got {list(fieldnames)}"
            )
            raise ValueError(message)
        _, summary = dedupe_comment_rows(reader)
    return summary


def write_deduped_comment_csv(
    source_path: Path,
    output_path: Path,
) -> CommentDedupeSummary:
    """Write a deterministic exact-row deduped closure comment CSV.

    Returns
    -------
    CommentDedupeSummary
        Dedupe counts and affected shortcodes for the written CSV.

    Raises
    ------
    ValueError
        The source file header does not match the authoritative closure schema.
    """
    with source_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != COMMENT_ROW_FIELDNAMES:
            message = (
                "comments.csv must use the closure schema "
                f"{list(COMMENT_ROW_FIELDNAMES)}, got {list(fieldnames)}"
            )
            raise ValueError(message)
        unique_rows, summary = dedupe_comment_rows(reader)

    header = list(COMMENT_ROW_FIELDNAMES)
    ensure_csv_with_header(output_path, header, reset=True)
    for row in unique_rows:
        append_csv_row(
            output_path,
            header,
            {field: row[field] for field in COMMENT_ROW_FIELDNAMES},
        )
    return summary
