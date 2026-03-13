# Copyright (c) 2026
"""Closure artifact classification for believerofbuckets task foundations."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

ArtifactPolicy = Literal["archive", "remove", "retain"]

AUTHORITATIVE_CLOSURE_ARTIFACT_NAMES = {
    "comments.csv",
    "downloads",
    "errors.csv",
    "posts.csv",
    "tool_dump.json",
}

NON_AUTHORITATIVE_COMPLETION_ARTIFACT_NAMES = {
    "checkpoint.json",
    "errors.ndjson",
    "extraction_errors.json",
    "summary.json",
}

_RETAIN_ARTIFACT_NAMES = AUTHORITATIVE_CLOSURE_ARTIFACT_NAMES | {
    "checkpoint_instaloader.json",
    "instagram_cookies.txt",
}

_ARCHIVE_ARTIFACT_NAMES = {
    ".cache",
    "SCRAPING_STATUS.md",
    "checkpoint.json",
    "errors.ndjson",
    "extraction_errors.json",
    "state.sqlite3",
    "stories.ndjson",
    "summary.json",
    "targets.ndjson",
    "users.ndjson",
}

_REMOVE_ARTIFACT_NAMES = {
    "checkpoint.json.lock",
    "comments.csv.lock",
    "errors.csv.lock",
    "errors.ndjson.lock",
    "posts.csv.lock",
    "summary.json.lock",
    "targets.ndjson.lock",
}


@dataclass(frozen=True, slots=True)
class ClosureArtifactInspection:
    """Computed authoritative closure counts for a scrape output tree."""

    authoritative_artifact_names: set[str]
    successful_shortcodes: int
    failing_shortcodes: int
    expected_shortcodes: int


def classify_artifact_name(name: str) -> ArtifactPolicy:
    """Return the stale-artifact policy for one artifact name.

    Returns
    -------
        The policy for the provided artifact name.
    """
    if name in _RETAIN_ARTIFACT_NAMES:
        return "retain"
    if name in _ARCHIVE_ARTIFACT_NAMES:
        return "archive"
    if name in _REMOVE_ARTIFACT_NAMES:
        return "remove"
    return "archive"


def classify_current_tree_artifacts(output_dir: Path) -> dict[str, ArtifactPolicy]:
    """Classify each artifact currently present in an output directory.

    Returns
    -------
        A policy map keyed by artifact name.
    """
    return {
        path.name: classify_artifact_name(path.name)
        for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
    }


def validate_authoritative_artifact_policy(
    policy_by_name: dict[str, ArtifactPolicy],
) -> None:
    """Ensure every authoritative closure artifact is present and retained.

    Raises
    ------
    ValueError
        Any authoritative artifact is missing or misclassified.
    """
    for name in sorted(AUTHORITATIVE_CLOSURE_ARTIFACT_NAMES):
        policy = policy_by_name.get(name)
        if policy is None:
            message = f"Missing authoritative artifact: {name}"
            raise ValueError(message)
        if policy != "retain":
            message = (
                f"Authoritative artifact '{name}' must use retain policy, "
                f"got '{policy}'"
            )
            raise ValueError(message)


def _count_csv_rows(path: Path) -> int:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _count_tool_dump_urls(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    urls = payload.get("urls")
    if not isinstance(urls, list):
        message = "Authoritative artifact 'tool_dump.json' must contain a urls list"
        raise TypeError(message)
    return len(urls)


def inspect_closure_artifacts(output_dir: Path) -> ClosureArtifactInspection:
    """Inspect authoritative artifacts and enforce final shortcode accounting.

    Returns
    -------
        The authoritative closure inspection for the output directory.

    Raises
    ------
    ValueError
        Authoritative artifacts are missing, misclassified, or mismatched.
    """
    policy_by_name = classify_current_tree_artifacts(output_dir)
    validate_authoritative_artifact_policy(policy_by_name)

    expected_shortcodes = _count_tool_dump_urls(output_dir / "tool_dump.json")
    successful_shortcodes = _count_csv_rows(output_dir / "posts.csv")
    failing_shortcodes = _count_csv_rows(output_dir / "errors.csv")

    if successful_shortcodes + failing_shortcodes != expected_shortcodes:
        message = (
            "Authoritative accounting mismatch: expected "
            f"{expected_shortcodes} shortcodes from tool_dump.json, found "
            f"{successful_shortcodes} successful shortcodes and "
            f"{failing_shortcodes} failing shortcodes"
        )
        raise ValueError(message)

    return ClosureArtifactInspection(
        authoritative_artifact_names=AUTHORITATIVE_CLOSURE_ARTIFACT_NAMES,
        successful_shortcodes=successful_shortcodes,
        failing_shortcodes=failing_shortcodes,
        expected_shortcodes=expected_shortcodes,
    )
