from __future__ import annotations

import csv
import json
import sys
from importlib import import_module
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

comment_dedupe = import_module("instagram_scraper.workflows.comment_dedupe")
comment_reconciliation = import_module(
    "instagram_scraper.workflows.comment_reconciliation",
)
COMMENT_ROW_FIELDNAMES = comment_dedupe.COMMENT_ROW_FIELDNAMES
reconcile_authoritative_comment_outputs = (
    comment_reconciliation.reconcile_authoritative_comment_outputs
)


def _write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, object]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def test_reconcile_authoritative_comment_outputs_dedupes_in_place_and_records_deltas(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "closure"
    output_dir.mkdir()
    comments_path = output_dir / "comments.csv"
    posts_path = output_dir / "posts.csv"
    summary_path = output_dir / "comment_reconciliation_summary.json"
    _write_csv(
        comments_path,
        list(COMMENT_ROW_FIELDNAMES),
        [
            {
                "post_shortcode": "AAA111",
                "id": "c1",
                "parent_id": "",
                "created_at_utc": "2026-03-10T00:00:00",
                "text": "same row",
                "comment_like_count": "0",
                "owner_username": "user1",
                "owner_id": "1",
            },
            {
                "post_shortcode": "AAA111",
                "id": "c1",
                "parent_id": "",
                "created_at_utc": "2026-03-10T00:00:00",
                "text": "same row",
                "comment_like_count": "0",
                "owner_username": "user1",
                "owner_id": "1",
            },
            {
                "post_shortcode": "AAA111",
                "id": "c1",
                "parent_id": "",
                "created_at_utc": "2026-03-10T00:00:00",
                "text": "edited row",
                "comment_like_count": "0",
                "owner_username": "user1",
                "owner_id": "1",
            },
            {
                "post_shortcode": "BBB222",
                "id": "c2",
                "parent_id": "",
                "created_at_utc": "2026-03-10T01:00:00",
                "text": "only row",
                "comment_like_count": "1",
                "owner_username": "user2",
                "owner_id": "2",
            },
        ],
    )
    _write_csv(
        posts_path,
        ["shortcode", "comments_count_reported"],
        [
            {"shortcode": "AAA111", "comments_count_reported": 4},
            {"shortcode": "BBB222", "comments_count_reported": 1},
            {"shortcode": "CCC333", "comments_count_reported": 2},
        ],
    )

    summary = reconcile_authoritative_comment_outputs(
        output_dir,
        summary_path=summary_path,
    )

    assert summary.before_row_count == 4
    assert summary.after_row_count == 3
    assert summary.removed_row_count == 1
    assert summary.affected_shortcodes == ("AAA111",)
    assert summary.matched_post_count == 1
    assert summary.mismatched_post_count == 2
    assert [mismatch.shortcode for mismatch in summary.mismatches] == [
        "AAA111",
        "CCC333",
    ]
    assert [mismatch.delta for mismatch in summary.mismatches] == [-2, -2]
    assert _read_csv(comments_path) == [
        {
            "post_shortcode": "AAA111",
            "id": "c1",
            "parent_id": "",
            "created_at_utc": "2026-03-10T00:00:00",
            "text": "same row",
            "comment_like_count": "0",
            "owner_username": "user1",
            "owner_id": "1",
        },
        {
            "post_shortcode": "AAA111",
            "id": "c1",
            "parent_id": "",
            "created_at_utc": "2026-03-10T00:00:00",
            "text": "edited row",
            "comment_like_count": "0",
            "owner_username": "user1",
            "owner_id": "1",
        },
        {
            "post_shortcode": "BBB222",
            "id": "c2",
            "parent_id": "",
            "created_at_utc": "2026-03-10T01:00:00",
            "text": "only row",
            "comment_like_count": "1",
            "owner_username": "user2",
            "owner_id": "2",
        },
    ]
    persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted_summary["before_row_count"] == 4
    assert persisted_summary["after_row_count"] == 3
    assert persisted_summary["removed_row_count"] == 1
    assert persisted_summary["affected_shortcodes"] == ["AAA111"]
    assert persisted_summary["matched_post_count"] == 1
    assert persisted_summary["mismatched_post_count"] == 2
    assert persisted_summary["mismatches"] == [
        {
            "comments_count_reported": 4,
            "deduped_comment_row_count": 2,
            "delta": -2,
            "shortcode": "AAA111",
        },
        {
            "comments_count_reported": 2,
            "deduped_comment_row_count": 0,
            "delta": -2,
            "shortcode": "CCC333",
        },
    ]


def test_reconciliation_failure_keeps_original_comments_csv(tmp_path: Path) -> None:
    output_dir = tmp_path / "closure"
    output_dir.mkdir()
    comments_path = output_dir / "comments.csv"
    posts_path = output_dir / "posts.csv"
    summary_path = output_dir / "comment_reconciliation_summary.json"
    rows = [
        {
            "post_shortcode": "AAA111",
            "id": "c1",
            "parent_id": "",
            "created_at_utc": "2026-03-10T00:00:00",
            "text": "same row",
            "comment_like_count": "0",
            "owner_username": "user1",
            "owner_id": "1",
        },
        {
            "post_shortcode": "AAA111",
            "id": "c1",
            "parent_id": "",
            "created_at_utc": "2026-03-10T00:00:00",
            "text": "same row",
            "comment_like_count": "0",
            "owner_username": "user1",
            "owner_id": "1",
        },
    ]
    _write_csv(comments_path, list(COMMENT_ROW_FIELDNAMES), rows)
    _write_csv(
        posts_path,
        ["shortcode", "comments_count_reported"],
        [{"shortcode": "AAA111", "comments_count_reported": "bad"}],
    )

    with pytest.raises(ValueError, match="non-integer comments_count_reported"):
        reconcile_authoritative_comment_outputs(output_dir, summary_path=summary_path)

    assert _read_csv(comments_path) == rows
    assert not summary_path.exists()
