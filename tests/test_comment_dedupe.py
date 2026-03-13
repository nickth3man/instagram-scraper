from __future__ import annotations

import csv
from pathlib import Path

from instagram_scraper.infrastructure.files import (
    append_csv_row,
    ensure_csv_with_header,
)
from instagram_scraper.workflows.comment_dedupe import (
    COMMENT_ROW_FIELDNAMES,
    audit_comment_csv,
    write_deduped_comment_csv,
)


def _write_comments_csv(path: Path, rows: list[dict[str, str]]) -> None:
    header = list(COMMENT_ROW_FIELDNAMES)
    ensure_csv_with_header(path, header, reset=True)
    for row in rows:
        append_csv_row(path, header, row)


def _read_comments_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def test_audit_comment_csv_reports_invariants(tmp_path: Path) -> None:
    source_path = tmp_path / "comments.csv"
    _write_comments_csv(
        source_path,
        [
            {
                "post_shortcode": "POST1",
                "id": "10",
                "parent_id": "",
                "created_at_utc": "2026-03-10T10:00:00",
                "text": "same row",
                "comment_like_count": "2",
                "owner_username": "alice",
                "owner_id": "101",
            },
            {
                "post_shortcode": "POST1",
                "id": "10",
                "parent_id": "",
                "created_at_utc": "2026-03-10T10:00:00",
                "text": "same row",
                "comment_like_count": "2",
                "owner_username": "alice",
                "owner_id": "101",
            },
        ],
    )

    summary = audit_comment_csv(source_path)

    assert summary.total_rows >= summary.unique_rows
    assert summary.removed_rows == summary.total_rows - summary.unique_rows
    assert isinstance(summary.affected_shortcodes, tuple)


def test_write_deduped_comment_csv_removes_only_exact_duplicate_rows(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "comments.csv"
    output_path = tmp_path / "comments.deduped.csv"
    rows = [
        {
            "post_shortcode": "POST1",
            "id": "10",
            "parent_id": "",
            "created_at_utc": "2026-03-10T10:00:00",
            "text": "same row",
            "comment_like_count": "2",
            "owner_username": "alice",
            "owner_id": "101",
        },
        {
            "post_shortcode": "POST1",
            "id": "10",
            "parent_id": "",
            "created_at_utc": "2026-03-10T10:00:00",
            "text": "same row",
            "comment_like_count": "2",
            "owner_username": "alice",
            "owner_id": "101",
        },
        {
            "post_shortcode": "POST1",
            "id": "10",
            "parent_id": "",
            "created_at_utc": "2026-03-10T10:00:00",
            "text": "same id, different text",
            "comment_like_count": "2",
            "owner_username": "alice",
            "owner_id": "101",
        },
        {
            "post_shortcode": "POST2",
            "id": "11",
            "parent_id": "10",
            "created_at_utc": "2026-03-10T10:02:00",
            "text": "reply",
            "comment_like_count": "0",
            "owner_username": "bob",
            "owner_id": "202",
        },
    ]
    _write_comments_csv(source_path, rows)

    summary = write_deduped_comment_csv(source_path, output_path)

    assert summary.total_rows == 4
    assert summary.unique_rows == 3
    assert summary.removed_rows == 1
    assert summary.affected_shortcodes == ("POST1",)
    assert _read_comments_csv(output_path) == [rows[0], rows[2], rows[3]]


def test_write_deduped_comment_csv_keeps_unique_rows_intact(tmp_path: Path) -> None:
    source_path = tmp_path / "comments.csv"
    output_path = tmp_path / "comments.deduped.csv"
    rows = [
        {
            "post_shortcode": "POST1",
            "id": "10",
            "parent_id": "",
            "created_at_utc": "2026-03-10T10:00:00",
            "text": "first",
            "comment_like_count": "2",
            "owner_username": "alice",
            "owner_id": "101",
        },
        {
            "post_shortcode": "POST1",
            "id": "10",
            "parent_id": "99",
            "created_at_utc": "2026-03-10T10:00:00",
            "text": "same id, different parent",
            "comment_like_count": "2",
            "owner_username": "alice",
            "owner_id": "101",
        },
        {
            "post_shortcode": "POST2",
            "id": "11",
            "parent_id": "",
            "created_at_utc": "2026-03-10T11:00:00",
            "text": "second",
            "comment_like_count": "0",
            "owner_username": "bob",
            "owner_id": "202",
        },
    ]
    _write_comments_csv(source_path, rows)

    summary = write_deduped_comment_csv(source_path, output_path)

    assert summary.total_rows == 3
    assert summary.unique_rows == 3
    assert summary.removed_rows == 0
    assert summary.affected_shortcodes == ()
    assert _read_comments_csv(output_path) == rows
