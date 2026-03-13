# Copyright (c) 2026
"""Apply authoritative comment dedupe and record reconciliation deltas."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from instagram_scraper.infrastructure.files import (
    append_csv_row,
    atomic_write_text,
    ensure_csv_with_header,
)
from instagram_scraper.workflows.comment_dedupe import (
    COMMENT_ROW_FIELDNAMES,
    dedupe_comment_rows,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class CommentCountMismatch:
    """Per-post delta between `posts.csv` and deduped `comments.csv`."""

    shortcode: str
    comments_count_reported: int
    deduped_comment_row_count: int
    delta: int


@dataclass(frozen=True, slots=True)
class CommentReconciliationSummary:
    """Durable summary of the authoritative dedupe and reconciliation pass."""

    generated_at_utc: str
    comments_csv: str
    posts_csv: str
    before_row_count: int
    after_row_count: int
    removed_row_count: int
    affected_shortcodes: tuple[str, ...]
    matched_post_count: int
    mismatched_post_count: int
    mismatches: tuple[CommentCountMismatch, ...]


def _read_comment_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != COMMENT_ROW_FIELDNAMES:
            message = (
                "comments.csv must use the closure schema "
                f"{list(COMMENT_ROW_FIELDNAMES)}, got {list(fieldnames)}"
            )
            raise ValueError(message)
        return [dict(row) for row in reader]


def _write_comment_rows(path: Path, rows: Sequence[dict[str, str]]) -> None:
    header = list(COMMENT_ROW_FIELDNAMES)
    ensure_csv_with_header(path, header, reset=True)
    for row in rows:
        append_csv_row(path, header, {field: row[field] for field in header})


def _read_post_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            message = "posts.csv is missing a header row"
            raise ValueError(message)
        required_headers = ("shortcode",)
        missing_headers: list[str] = [
            header for header in required_headers if header not in reader.fieldnames
        ]
        if (
            "comments_count_reported" not in reader.fieldnames
            and "comment_count" not in reader.fieldnames
        ):
            missing_headers.append("comments_count_reported|comment_count")
        if missing_headers:
            message = "posts.csv is missing required headers: " + ", ".join(
                missing_headers,
            )
            raise ValueError(message)
        comment_field = (
            "comments_count_reported"
            if "comments_count_reported" in reader.fieldnames
            else "comment_count"
        )
        rows = [dict(row) for row in reader]
        for row in rows:
            row["comments_count_reported"] = row.get(comment_field, "")
        return rows


def _build_mismatches(
    post_rows: list[dict[str, str]],
    deduped_rows: Sequence[dict[str, str]],
) -> tuple[CommentCountMismatch, ...]:
    counts_by_shortcode = Counter(row["post_shortcode"] for row in deduped_rows)
    mismatches: list[CommentCountMismatch] = []
    for row in post_rows:
        shortcode = row["shortcode"]
        try:
            reported = int(row["comments_count_reported"])
        except ValueError as exc:
            message = (
                "posts.csv has a non-integer comments_count_reported value for "
                f"{shortcode}: {row['comments_count_reported']}"
            )
            raise ValueError(message) from exc
        observed = counts_by_shortcode.get(shortcode, 0)
        if observed == reported:
            continue
        mismatches.append(
            CommentCountMismatch(
                shortcode=shortcode,
                comments_count_reported=reported,
                deduped_comment_row_count=observed,
                delta=observed - reported,
            ),
        )
    return tuple(mismatches)


def reconcile_authoritative_comment_outputs(
    output_dir: Path,
    *,
    summary_path: Path | None = None,
) -> CommentReconciliationSummary:
    """Dedupe authoritative comments.csv in place and record reconciliation.

    Parameters
    ----------
    output_dir
        Directory containing authoritative `comments.csv` and `posts.csv` outputs.
    summary_path
        Optional destination for the JSON reconciliation summary. Defaults to
        `output_dir / "comment_reconciliation_summary.json"`.

    Returns
    -------
    CommentReconciliationSummary
        Dedupe totals and any remaining post-level mismatches after mutation.
    """
    comments_path = output_dir / "comments.csv"
    posts_path = output_dir / "posts.csv"
    resolved_summary_path = (
        summary_path
        if summary_path is not None
        else output_dir / "comment_reconciliation_summary.json"
    )

    comment_rows = _read_comment_rows(comments_path)
    deduped_rows, dedupe_summary = dedupe_comment_rows(comment_rows)
    deduped_row_dicts = [
        {field: str(row[field]) for field in COMMENT_ROW_FIELDNAMES}
        for row in deduped_rows
    ]
    post_rows = _read_post_rows(posts_path)
    mismatches = _build_mismatches(post_rows, deduped_row_dicts)
    summary = CommentReconciliationSummary(
        generated_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        comments_csv=str(comments_path),
        posts_csv=str(posts_path),
        before_row_count=dedupe_summary.total_rows,
        after_row_count=dedupe_summary.unique_rows,
        removed_row_count=dedupe_summary.removed_rows,
        affected_shortcodes=dedupe_summary.affected_shortcodes,
        matched_post_count=len(post_rows) - len(mismatches),
        mismatched_post_count=len(mismatches),
        mismatches=mismatches,
    )
    temp_comments_path = comments_path.with_suffix(".csv.tmp")
    _write_comment_rows(temp_comments_path, deduped_row_dicts)
    atomic_write_text(
        resolved_summary_path,
        json.dumps(asdict(summary), indent=2, sort_keys=True),
    )
    temp_comments_path.replace(comments_path)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dedupe authoritative comments.csv and reconcile post totals",
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--summary-path", type=Path)
    return parser


def _main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    summary = reconcile_authoritative_comment_outputs(
        args.output_dir,
        summary_path=args.summary_path,
    )
    sys.stdout.write(json.dumps(asdict(summary), indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
