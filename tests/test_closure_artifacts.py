from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from instagram_scraper.exceptions import InstagramError
from instagram_scraper.workflows.closure_artifacts import (
    AUTHORITATIVE_CLOSURE_ARTIFACT_NAMES,
    NON_AUTHORITATIVE_COMPLETION_ARTIFACT_NAMES,
    ArtifactPolicy,
    classify_current_tree_artifacts,
    inspect_closure_artifacts,
    validate_authoritative_artifact_policy,
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


def _write_authoritative_fixture(
    output_dir: Path,
    *,
    urls: list[str],
    post_rows: list[dict[str, object]],
    error_rows: list[dict[str, object]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "downloads").mkdir()
    (output_dir / "tool_dump.json").write_text(
        json.dumps({"urls": urls}),
        encoding="utf-8",
    )
    _write_csv(
        output_dir / "posts.csv",
        ["shortcode", "post_url"],
        post_rows,
    )
    _write_csv(
        output_dir / "comments.csv",
        ["post_shortcode", "id"],
        [],
    )
    _write_csv(
        output_dir / "errors.csv",
        ["index", "post_url", "shortcode", "stage", "error"],
        error_rows,
    )


def test_inspect_closure_artifacts_uses_real_believerofbuckets_tree() -> None:
    output_dir = Path("data/believerofbuckets")

    inspection = inspect_closure_artifacts(output_dir)
    policy_by_name = classify_current_tree_artifacts(output_dir)

    assert {
        "comments.csv",
        "downloads",
        "errors.csv",
        "posts.csv",
        "tool_dump.json",
    } == AUTHORITATIVE_CLOSURE_ARTIFACT_NAMES
    assert {
        "checkpoint.json",
        "errors.ndjson",
        "extraction_errors.json",
        "summary.json",
    } == NON_AUTHORITATIVE_COMPLETION_ARTIFACT_NAMES
    assert inspection.successful_shortcodes == 99
    assert inspection.failing_shortcodes == 1
    assert inspection.expected_shortcodes == 100
    assert (
        inspection.authoritative_artifact_names == AUTHORITATIVE_CLOSURE_ARTIFACT_NAMES
    )
    assert policy_by_name["tool_dump.json"] == "retain"
    assert policy_by_name["posts.csv"] == "retain"
    assert policy_by_name["comments.csv"] == "retain"
    assert policy_by_name["errors.csv"] == "retain"
    assert policy_by_name["downloads"] == "retain"
    assert "summary.json" not in policy_by_name
    assert "checkpoint.json" not in policy_by_name
    assert "errors.ndjson" not in policy_by_name
    assert "extraction_errors.json" not in policy_by_name
    assert "checkpoint.json.lock" not in policy_by_name
    assert "comments.csv.lock" not in policy_by_name
    assert "errors.csv.lock" not in policy_by_name
    assert "posts.csv.lock" not in policy_by_name
    assert "summary.json.lock" not in policy_by_name
    assert policy_by_name["instagram_cookies.txt"] == "retain"
    assert policy_by_name["checkpoint_instaloader.json"] == "retain"
    assert "SCRAPING_STATUS.md" not in policy_by_name
    assert "state.sqlite3" not in policy_by_name
    assert "stories.ndjson" not in policy_by_name
    assert "targets.ndjson" not in policy_by_name
    assert "users.ndjson" not in policy_by_name
    assert ".cache" not in policy_by_name


def test_inspect_closure_artifacts_rejects_missing_authoritative_artifact(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "closure"
    _write_authoritative_fixture(
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
    )
    (output_dir / "errors.csv").unlink()

    with pytest.raises(
        InstagramError,
        match=re.escape("Missing authoritative artifact: errors.csv"),
    ):
        inspect_closure_artifacts(output_dir)


def test_validate_authoritative_artifact_policy_rejects_misclassification() -> None:
    policy_by_name: dict[str, ArtifactPolicy] = dict.fromkeys(
        AUTHORITATIVE_CLOSURE_ARTIFACT_NAMES,
        "retain",
    )
    policy_by_name["posts.csv"] = "archive"

    with pytest.raises(
        InstagramError,
        match=re.escape(
            "Authoritative artifact 'posts.csv' must use retain policy, got 'archive'",
        ),
    ):
        validate_authoritative_artifact_policy(policy_by_name)


def test_inspect_closure_artifacts_rejects_accounting_mismatch(tmp_path: Path) -> None:
    output_dir = tmp_path / "closure"
    _write_authoritative_fixture(
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
        ],
        error_rows=[],
    )

    with pytest.raises(
        InstagramError,
        match=re.escape(
            "Authoritative accounting mismatch: expected 2 shortcodes from "
            "tool_dump.json, found 1 successful shortcodes and 0 failing shortcodes",
        ),
    ):
        inspect_closure_artifacts(output_dir)
