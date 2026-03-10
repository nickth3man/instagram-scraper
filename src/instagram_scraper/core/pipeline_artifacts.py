# Copyright (c) 2026
"""Artifact preparation and normalization helpers for the unified pipeline."""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, cast

from instagram_scraper.infrastructure.files import write_json_line
from instagram_scraper.models import (
    CommentRecord,
    PostRecord,
    RawCaptureRecord,
    TargetRecord,
    UserRecord,
)
from instagram_scraper.storage.database import record_target

if TYPE_CHECKING:
    from pathlib import Path

    from instagram_scraper.storage.database import MetadataStore


STANDARD_ARTIFACTS = (
    "targets.ndjson",
    "users.ndjson",
    "posts.ndjson",
    "comments.ndjson",
    "stories.ndjson",
    "errors.ndjson",
)


def prepare_output_dir(
    output_dir: Path,
    *,
    reset_output: bool,
) -> dict[str, Path]:
    """Create or reset the standard pipeline artifact files.

    Returns
    -------
    dict[str, Path]
        The standard artifact paths keyed by logical artifact name.

    """
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    if reset_output and summary_path.exists():
        summary_path.unlink()
    paths = {"summary": summary_path}
    for artifact_name in STANDARD_ARTIFACTS:
        path = output_dir / artifact_name
        if reset_output and path.exists():
            path.unlink()
        if reset_output or not path.exists():
            path.write_text("", encoding="utf-8")
        paths[artifact_name.removesuffix(".ndjson")] = path
    return paths


def write_targets(
    path: Path,
    targets: list[TargetRecord],
    store: MetadataStore,
) -> None:
    """Persist resolved targets to NDJSON and the metadata store."""
    for target in targets:
        payload = target.model_dump(mode="json")
        write_json_line(path, payload)
        record_target(
            store,
            kind=target.target_kind,
            normalized_key=f"{target.target_kind}:{target.target_value}",
        )


def populate_normalized_artifacts(
    mode: str,
    output_dir: Path,
    artifact_paths: dict[str, Path],
) -> None:
    """Backfill standardized NDJSON artifacts for supported modes."""
    if mode == "profile":
        _populate_profile_artifacts(output_dir, artifact_paths)


def record_raw_captures(mode: str, output_dir: Path) -> None:
    """Persist raw-capture manifests for modes that support them."""
    if mode == "profile":
        _record_profile_raw_capture(output_dir)


def _populate_profile_artifacts(
    output_dir: Path,
    artifact_paths: dict[str, Path],
) -> None:
    payload = _load_profile_dataset(output_dir)
    if payload is None:
        return
    _write_profile_user(payload, artifact_paths["users"])
    posts = payload.get("posts")
    if not isinstance(posts, list):
        return
    for post in posts:
        if not isinstance(post, dict):
            continue
        _write_profile_post_and_comments(
            cast("dict[str, object]", post),
            artifact_paths,
        )


def _record_profile_raw_capture(output_dir: Path) -> None:
    dataset_path = output_dir / "instagram_dataset.json"
    if not dataset_path.exists():
        return
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    capture_path = raw_dir / dataset_path.name
    shutil.copy2(dataset_path, capture_path)
    write_json_line(
        output_dir / "raw_captures.ndjson",
        RawCaptureRecord(
            provider="instaloader",
            target=f"profile:{output_dir.name}",
            path=capture_path,
            source_endpoint="legacy_profile_dataset",
        ).model_dump(mode="json"),
    )


def _load_profile_dataset(output_dir: Path) -> dict[str, object] | None:
    dataset_path = output_dir / "instagram_dataset.json"
    if not dataset_path.exists():
        return None
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _write_profile_user(payload: dict[str, object], path: Path) -> None:
    username = payload.get("target_profile")
    if not isinstance(username, str):
        return
    write_json_line(
        path,
        UserRecord(
            provider="instaloader",
            target_kind="profile",
            username=username,
        ).model_dump(mode="json"),
    )


def _write_profile_post_and_comments(
    post: dict[str, object],
    artifact_paths: dict[str, Path],
) -> None:
    post_payload = _profile_post_record(post)
    if post_payload is None:
        return
    write_json_line(artifact_paths["posts"], post_payload.model_dump(mode="json"))
    comments = post.get("comments")
    if not isinstance(comments, list):
        return
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        comment_payload = _profile_comment_record(
            cast("dict[str, object]", comment),
            post_payload.shortcode,
        )
        if comment_payload is None:
            continue
        write_json_line(
            artifact_paths["comments"],
            comment_payload.model_dump(mode="json"),
        )


def _profile_post_record(post: dict[str, object]) -> PostRecord | None:
    shortcode = post.get("shortcode")
    post_url = post.get("post_url")
    if not isinstance(shortcode, str) or not isinstance(post_url, str):
        return None
    owner_username = post.get("owner_username")
    taken_at_utc = post.get("date_utc")
    return PostRecord.model_validate(
        {
            "provider": "instaloader",
            "target_kind": "profile",
            "shortcode": shortcode,
            "post_url": post_url,
            "owner_username": (
                owner_username if isinstance(owner_username, str) else None
            ),
            "taken_at_utc": taken_at_utc if isinstance(taken_at_utc, str) else None,
        },
    )


def _profile_comment_record(
    comment: dict[str, object],
    shortcode: str,
) -> CommentRecord | None:
    comment_id = comment.get("id")
    if not isinstance(comment_id, str):
        return None
    owner_username = comment.get("owner_username")
    text = comment.get("text")
    taken_at_utc = comment.get("created_at_utc")
    return CommentRecord.model_validate(
        {
            "provider": "instaloader",
            "target_kind": "comment",
            "comment_id": comment_id,
            "post_shortcode": shortcode,
            "owner_username": (
                owner_username if isinstance(owner_username, str) else None
            ),
            "text": text if isinstance(text, str) else None,
            "taken_at_utc": taken_at_utc if isinstance(taken_at_utc, str) else None,
        },
    )
