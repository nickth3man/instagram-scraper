# Copyright (c) 2026
"""Disk-based closure audit for authoritative closure artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from instagram_scraper.workflows.closure_artifacts import (
    classify_current_tree_artifacts,
    validate_authoritative_artifact_policy,
)
from instagram_scraper.workflows.comment_dedupe import comment_row_key

_SHORTCODE_URL_PATTERN = re.compile(r"/([A-Za-z0-9_-]+)/?$")
_DOWNLOAD_SUFFIX_PATTERN = re.compile(r"^(?P<shortcode>.+?)(?:_\d+)?$")


@dataclass(frozen=True, slots=True)
class ClosureAudit:
    """Authoritative closure counts recomputed from on-disk artifacts."""

    input_url_count: int
    successful_post_count: int
    failing_shortcode_count: int
    duplicate_post_row_count: int
    duplicate_comment_row_count: int
    download_base_count: int


def _load_tool_dump_urls(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    urls = payload.get("urls")
    if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
        message = "tool_dump.json must contain a urls list of strings"
        raise ValueError(message)
    return urls


def _read_validated_csv_rows(
    path: Path,
    *,
    required_headers: tuple[str, ...],
    required_non_blank_fields: tuple[str, ...],
) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            message = f"{path.name} is missing a header row"
            raise ValueError(message)

        missing_headers = [
            header for header in required_headers if header not in reader.fieldnames
        ]
        if missing_headers:
            formatted_headers = ", ".join(missing_headers)
            message = f"{path.name} is missing required headers: {formatted_headers}"
            raise ValueError(message)

        rows: list[dict[str, str]] = []
        for row_number, row in enumerate(reader, start=2):
            partial_fields = [
                field
                for field in required_headers
                if row.get(field) is None
            ]
            if partial_fields:
                formatted_fields = ", ".join(partial_fields)
                message = (
                    f"{path.name} row {row_number} is partial; missing fields: "
                    f"{formatted_fields}"
                )
                raise ValueError(message)

            blank_fields = [
                field
                for field in required_non_blank_fields
                if not row[field].strip()
            ]
            if blank_fields:
                formatted_fields = ", ".join(blank_fields)
                message = (
                    f"{path.name} row {row_number} has blank required fields: "
                    f"{formatted_fields}"
                )
                raise ValueError(message)

            normalized_row = {
                fieldname: (value if value is not None else "")
                for fieldname, value in row.items()
            }
            rows.append(normalized_row)

    return rows


def _count_duplicate_post_rows(rows: list[dict[str, str]]) -> tuple[int, int]:
    counts = Counter(row["shortcode"] for row in rows)
    unique_count = len(counts)
    duplicate_row_count = sum(count - 1 for count in counts.values() if count > 1)
    return unique_count, duplicate_row_count


def _count_duplicate_comment_rows(rows: list[dict[str, str]]) -> int:
    counts = Counter(comment_row_key(row) for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def _count_unique_error_shortcodes(rows: list[dict[str, str]]) -> int:
    return len({row["shortcode"] for row in rows})


def _extract_shortcode_from_url(url: str) -> str:
    stripped_url = url.rstrip("/")
    match = _SHORTCODE_URL_PATTERN.search(stripped_url)
    if match is None:
        message = f"tool_dump.json contains an unparseable Instagram URL: {url}"
        raise ValueError(message)
    return match.group(1)


def _count_download_bases(downloads_dir: Path) -> int:
    download_bases: set[str] = set()
    for file_path in downloads_dir.rglob("*"):
        if not file_path.is_file():
            continue
        stem = file_path.stem
        match = _DOWNLOAD_SUFFIX_PATTERN.fullmatch(stem)
        shortcode = match.group("shortcode") if match is not None else ""
        if not shortcode:
            message = (
                "downloads contains a file with an unrecognized basename pattern: "
                f"{file_path.name}"
            )
            raise ValueError(message)
        download_bases.add(shortcode)
    return len(download_bases)


def _validate_reconciliation(
    input_url_count: int,
    input_shortcodes: set[str],
    post_shortcodes: set[str],
    error_shortcodes: set[str],
    observed_counts: tuple[int, int],
) -> None:
    successful_post_count, failing_shortcode_count = observed_counts
    duplicate_input_shortcode_count = input_url_count - len(input_shortcodes)
    if duplicate_input_shortcode_count > 0:
        message = (
            "tool_dump.json contains duplicate shortcode URLs; authoritative "
            f"input count is ambiguous across {duplicate_input_shortcode_count} rows"
        )
        raise ValueError(message)

    overlapping_shortcodes = sorted(post_shortcodes & error_shortcodes)
    if overlapping_shortcodes:
        formatted_shortcodes = ", ".join(overlapping_shortcodes)
        message = (
            "Closure audit found shortcodes present in both posts.csv and "
            f"errors.csv: {formatted_shortcodes}"
        )
        raise ValueError(message)

    missing_shortcodes = sorted(input_shortcodes - post_shortcodes - error_shortcodes)
    unexpected_shortcodes = sorted(
        (post_shortcodes | error_shortcodes) - input_shortcodes,
    )
    if missing_shortcodes or unexpected_shortcodes:
        message_parts = ["Closure audit shortcode reconciliation mismatch"]
        if missing_shortcodes:
            message_parts.append(
                "missing from posts/errors: " + ", ".join(missing_shortcodes),
            )
        if unexpected_shortcodes:
            message_parts.append(
                "not present in tool_dump.json: " + ", ".join(unexpected_shortcodes),
            )
        raise ValueError("; ".join(message_parts))

    if successful_post_count + failing_shortcode_count != input_url_count:
        message = (
            "Closure audit accounting mismatch: expected "
            f"{input_url_count} input URLs, found {successful_post_count} unique "
            f"successful posts and {failing_shortcode_count} unique failing shortcodes"
        )
        raise ValueError(message)


def audit_closure_output(output_dir: Path) -> ClosureAudit:
    """Audit authoritative closure artifacts from disk only.

    Parameters
    ----------
    output_dir
        Scrape output directory containing authoritative closure artifacts.

    Returns
    -------
    ClosureAudit
        Recomputed authoritative counts and duplicate metrics.

    """
    policy_by_name = classify_current_tree_artifacts(output_dir)
    validate_authoritative_artifact_policy(policy_by_name)

    input_urls = _load_tool_dump_urls(output_dir / "tool_dump.json")
    input_url_count = len(input_urls)
    input_shortcodes = {_extract_shortcode_from_url(url) for url in input_urls}

    post_rows = _read_validated_csv_rows(
        output_dir / "posts.csv",
        required_headers=("shortcode", "post_url"),
        required_non_blank_fields=("shortcode", "post_url"),
    )
    error_rows = _read_validated_csv_rows(
        output_dir / "errors.csv",
        required_headers=("shortcode", "post_url", "stage", "error"),
        required_non_blank_fields=("shortcode", "post_url", "stage", "error"),
    )
    comment_rows = _read_validated_csv_rows(
        output_dir / "comments.csv",
        required_headers=("post_shortcode", "id"),
        required_non_blank_fields=("post_shortcode", "id"),
    )

    successful_post_count, duplicate_post_row_count = _count_duplicate_post_rows(
        post_rows,
    )
    failing_shortcode_count = _count_unique_error_shortcodes(error_rows)
    duplicate_comment_row_count = _count_duplicate_comment_rows(comment_rows)
    download_base_count = _count_download_bases(output_dir / "downloads")

    post_shortcodes = {row["shortcode"] for row in post_rows}
    error_shortcodes = {row["shortcode"] for row in error_rows}
    _validate_reconciliation(
        input_url_count,
        input_shortcodes,
        post_shortcodes,
        error_shortcodes,
        (successful_post_count, failing_shortcode_count),
    )

    return ClosureAudit(
        input_url_count=input_url_count,
        successful_post_count=successful_post_count,
        failing_shortcode_count=failing_shortcode_count,
        duplicate_post_row_count=duplicate_post_row_count,
        duplicate_comment_row_count=duplicate_comment_row_count,
        download_base_count=download_base_count,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit authoritative closure artifacts from disk",
    )
    parser.add_argument("output_dir", type=Path)
    return parser


def _main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    audit = audit_closure_output(args.output_dir)
    sys.stdout.write(json.dumps(asdict(audit), indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
