from __future__ import annotations

import csv
import json
import re
import sys
from importlib import import_module
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

closure_audit = import_module("instagram_scraper.workflows.closure_audit")
comment_dedupe = import_module("instagram_scraper.workflows.comment_dedupe")
audit_closure_output = closure_audit.audit_closure_output
COMMENT_ROW_FIELDNAMES = comment_dedupe.COMMENT_ROW_FIELDNAMES


def _write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, object]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_audit_fixture(
    output_dir: Path,
    *,
    urls: list[str],
    post_rows: list[dict[str, object]],
    comment_rows: list[dict[str, object]],
    error_rows: list[dict[str, object]],
    download_filenames: list[str],
) -> None:
    downloads_dir = output_dir / "downloads" / "fixture"
    downloads_dir.mkdir(parents=True)
    (output_dir / "tool_dump.json").write_text(
        json.dumps({"urls": urls}),
        encoding="utf-8",
    )
    _write_csv(output_dir / "posts.csv", ["shortcode", "post_url"], post_rows)
    _write_csv(
        output_dir / "comments.csv",
        list(COMMENT_ROW_FIELDNAMES),
        comment_rows,
    )
    _write_csv(
        output_dir / "errors.csv",
        ["index", "post_url", "shortcode", "stage", "error"],
        error_rows,
    )
    for filename in download_filenames:
        (downloads_dir / filename).write_text("fixture", encoding="utf-8")


def test_audit_closure_output_uses_real_believerofbuckets_tree() -> None:
    audit = audit_closure_output(Path("data/believerofbuckets"))

    assert audit.input_url_count == 100
    assert audit.successful_post_count == 99
    assert audit.failing_shortcode_count == 1
    assert audit.duplicate_post_row_count == 0
    assert audit.duplicate_comment_row_count == 0
    assert audit.download_base_count == 99


def test_audit_closure_output_counts_duplicate_rows_without_using_stale_files(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "closure"
    _write_audit_fixture(
        output_dir,
        urls=[
            "https://www.instagram.com/p/AAA111/",
            "https://www.instagram.com/p/BBB222/",
        ],
        post_rows=[
            {
                "shortcode": "AAA111",
                "post_url": "https://www.instagram.com/p/AAA111/",
            },
            {
                "shortcode": "AAA111",
                "post_url": "https://www.instagram.com/p/AAA111/",
            },
        ],
        comment_rows=[
            {
                "post_shortcode": "AAA111",
                "id": "c1",
                "parent_id": "",
                "created_at_utc": "2026-03-10T00:00:00",
                "text": "same row",
                "comment_like_count": "0",
                "owner_username": "user",
                "owner_id": "1",
            },
            {
                "post_shortcode": "AAA111",
                "id": "c1",
                "parent_id": "",
                "created_at_utc": "2026-03-10T00:00:00",
                "text": "same row",
                "comment_like_count": "0",
                "owner_username": "user",
                "owner_id": "1",
            },
        ],
        error_rows=[
            {
                "index": 1,
                "post_url": "https://www.instagram.com/p/BBB222/",
                "shortcode": "BBB222",
                "stage": "extract_post",
                "error": "BadResponseException",
            },
        ],
        download_filenames=["AAA111.jpg", "AAA111.txt"],
    )
    (output_dir / "summary.json").write_text(
        json.dumps({"successful_posts": 5000}),
        encoding="utf-8",
    )
    (output_dir / "checkpoint.json").write_text(
        json.dumps({"completed": ["AAA111", "BBB222", "CCC333"]}),
        encoding="utf-8",
    )

    audit = audit_closure_output(output_dir)

    assert audit.input_url_count == 2
    assert audit.successful_post_count == 1
    assert audit.failing_shortcode_count == 1
    assert audit.duplicate_post_row_count == 1
    assert audit.duplicate_comment_row_count == 1
    assert audit.download_base_count == 1


def test_audit_closure_output_treats_same_id_different_text_comments_as_unique(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "closure"
    _write_audit_fixture(
        output_dir,
        urls=["https://www.instagram.com/p/AAA111/"],
        post_rows=[
            {
                "shortcode": "AAA111",
                "post_url": "https://www.instagram.com/p/AAA111/",
            },
        ],
        comment_rows=[
            {
                "post_shortcode": "AAA111",
                "id": "c1",
                "parent_id": "",
                "created_at_utc": "2026-03-10T00:00:00",
                "text": "first text",
                "comment_like_count": "0",
                "owner_username": "user",
                "owner_id": "1",
            },
            {
                "post_shortcode": "AAA111",
                "id": "c1",
                "parent_id": "",
                "created_at_utc": "2026-03-10T00:00:00",
                "text": "edited text",
                "comment_like_count": "0",
                "owner_username": "user",
                "owner_id": "1",
            },
        ],
        error_rows=[],
        download_filenames=["AAA111.jpg"],
    )

    audit = audit_closure_output(output_dir)

    assert audit.duplicate_comment_row_count == 0


def test_audit_closure_output_rejects_posts_csv_missing_required_headers(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "closure"
    _write_audit_fixture(
        output_dir,
        urls=["https://www.instagram.com/p/AAA111/"],
        post_rows=[
            {
                "shortcode": "AAA111",
                "post_url": "https://www.instagram.com/p/AAA111/",
            },
        ],
        comment_rows=[],
        error_rows=[],
        download_filenames=["AAA111.jpg"],
    )
    (output_dir / "posts.csv").write_text(
        "shortcode\nAAA111\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=re.escape("posts.csv is missing required headers: post_url"),
    ):
        audit_closure_output(output_dir)


def test_audit_closure_output_rejects_partial_comments_csv_rows(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "closure"
    _write_audit_fixture(
        output_dir,
        urls=["https://www.instagram.com/p/AAA111/"],
        post_rows=[
            {
                "shortcode": "AAA111",
                "post_url": "https://www.instagram.com/p/AAA111/",
            },
        ],
        comment_rows=[],
        error_rows=[],
        download_filenames=["AAA111.jpg"],
    )
    (output_dir / "comments.csv").write_text(
        "post_shortcode,id\nAAA111\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=re.escape(
            "comments.csv is missing required headers: parent_id, created_at_utc, "
            "text, comment_like_count, owner_username, owner_id",
        ),
    ):
        audit_closure_output(output_dir)


def test_audit_closure_output_rejects_blank_required_error_fields(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "closure"
    _write_audit_fixture(
        output_dir,
        urls=["https://www.instagram.com/p/AAA111/"],
        post_rows=[],
        comment_rows=[],
        error_rows=[],
        download_filenames=[],
    )
    (output_dir / "errors.csv").write_text(
        "index,post_url,shortcode,stage,error\n0,https://www.instagram.com/p/AAA111/,AAA111,extract_post,\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=re.escape("errors.csv row 2 has blank required fields: error"),
    ):
        audit_closure_output(output_dir)
