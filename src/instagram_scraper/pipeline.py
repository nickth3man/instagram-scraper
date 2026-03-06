# Copyright (c) 2026
"""Unified provider dispatch and artifact orchestration for scrape runs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast
from uuid import uuid4

from rich.console import Console

from instagram_scraper._shared_io import atomic_write_text, write_json_line
from instagram_scraper.cache import ScraperCache
from instagram_scraper.capabilities import (
    describe_mode_capability,
    ensure_mode_is_runnable,
)
from instagram_scraper.logging_utils import build_logger
from instagram_scraper.models import (
    CommentRecord,
    PostRecord,
    RawCaptureRecord,
    RunSummary,
    TargetRecord,
    UserRecord,
)
from instagram_scraper.presentation import render_run_summary
from instagram_scraper.providers.follow_graph import FollowGraphProvider
from instagram_scraper.providers.hashtag import HashtagScrapeProvider
from instagram_scraper.providers.interactions import CommentersProvider, LikersProvider
from instagram_scraper.providers.location import LocationScrapeProvider
from instagram_scraper.providers.profile import ProfileScrapeProvider
from instagram_scraper.providers.stories import StoriesProvider
from instagram_scraper.providers.url import UrlScrapeProvider
from instagram_scraper.storage_db import MetadataStore, create_store, record_target

STANDARD_ARTIFACTS = (
    "targets.ndjson",
    "users.ndjson",
    "posts.ndjson",
    "comments.ndjson",
    "stories.ndjson",
    "errors.ndjson",
)


def run_pipeline(mode: str, **kwargs: object) -> int:
    """Validate, execute, and render the requested scrape mode.

    Returns
    -------
    int
        Process exit code `0` when the pipeline completes successfully.

    """
    execute_pipeline(mode, **kwargs)
    return 0


def execute_pipeline(mode: str, **kwargs: object) -> RunSummary:
    """Execute a unified scrape mode and persist normalized artifacts.

    Returns
    -------
    RunSummary
        The normalized summary for the completed pipeline run.

    Raises
    ------
    TypeError
        Raised when the selected provider does not return `RunSummary`.

    """
    descriptor = describe_mode_capability(mode)
    has_auth = bool(kwargs.get("has_auth"))
    ensure_mode_is_runnable(mode, has_auth=has_auth)
    output_dir = _resolve_output_dir(mode, kwargs)
    reset_output = bool(kwargs.get("reset_output"))
    artifact_paths = _prepare_output_dir(output_dir, reset_output=reset_output)
    store = create_store(output_dir / "state.sqlite3")
    run_id = str(kwargs.get("run_id") or f"{mode}-{uuid4().hex[:8]}")
    logger = build_logger(run_id=run_id, mode=mode)
    cache = ScraperCache(output_dir / ".cache")
    cache.set("last_mode", mode)
    logger.info(
        "pipeline_started",
        support_tier=descriptor.support_tier,
        output_dir=str(output_dir),
    )
    targets = _resolve_targets(mode, kwargs)
    _write_targets(artifact_paths["targets"], targets, store)
    summary = _run_mode(mode, {**kwargs, "output_dir": output_dir})
    if not isinstance(summary, RunSummary):
        message = f"Provider for mode {mode} did not return RunSummary"
        raise TypeError(message)
    _populate_normalized_artifacts(mode, output_dir, artifact_paths)
    if bool(kwargs.get("raw_captures")):
        _record_raw_captures(mode, output_dir)
    normalized_summary = summary.model_copy(
        update={
            "run_id": run_id,
            "output_dir": output_dir,
            "targets": len(targets),
            "support_tier": descriptor.support_tier,
            "requires_auth": descriptor.requires_auth,
        },
    )
    atomic_write_text(
        artifact_paths["summary"],
        normalized_summary.model_dump_json(indent=2),
    )
    render_run_summary(Console(), normalized_summary)
    logger.info(
        "pipeline_completed",
        targets=normalized_summary.targets,
        users=normalized_summary.users,
        posts=normalized_summary.posts,
        comments=normalized_summary.comments,
        stories=normalized_summary.stories,
        errors=normalized_summary.errors,
    )
    return normalized_summary


def default_output_dir(mode: str) -> Path:
    """Return the default output directory for a mode.

    Returns
    -------
    Path
        The mode-specific default directory under `data/`.

    """
    return Path("data") / mode


def _resolve_output_dir(mode: str, kwargs: dict[str, object]) -> Path:
    output_dir = kwargs.get("output_dir")
    if isinstance(output_dir, Path):
        return output_dir
    if mode == "profile" and isinstance(kwargs.get("username"), str):
        return Path("data") / str(kwargs["username"])
    if mode == "url" and isinstance(kwargs.get("post_url"), str):
        shortcode = str(kwargs["post_url"]).rstrip("/").split("/")[-1] or "url"
        return Path("data") / shortcode
    return default_output_dir(mode)


def _prepare_output_dir(
    output_dir: Path,
    *,
    reset_output: bool,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    if reset_output and summary_path.exists():
        summary_path.unlink()
    paths = {"summary": summary_path}
    for artifact_name in STANDARD_ARTIFACTS:
        path = output_dir / artifact_name
        if reset_output and path.exists():
            path.unlink()
        path.write_text("", encoding="utf-8")
        paths[artifact_name.removesuffix(".ndjson")] = path
    return paths


def _write_targets(
    path: Path,
    targets: list[TargetRecord],
    store: MetadataStore,
) -> None:
    for target in targets:
        payload = target.model_dump(mode="json")
        write_json_line(path, payload)
        record_target(
            store,
            kind=target.target_kind,
            normalized_key=f"{target.target_kind}:{target.target_value}",
        )


def _populate_normalized_artifacts(
    mode: str,
    output_dir: Path,
    artifact_paths: dict[str, Path],
) -> None:
    if mode == "profile":
        _populate_profile_artifacts(output_dir, artifact_paths)


def _populate_profile_artifacts(
    output_dir: Path,
    artifact_paths: dict[str, Path],
) -> None:
    payload = _load_profile_dataset(output_dir)
    if payload is None:
        return
    _write_profile_user(payload, output_dir)
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


def _record_raw_captures(mode: str, output_dir: Path) -> None:
    if mode == "profile":
        _record_profile_raw_capture(output_dir)


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


def _write_profile_user(payload: dict[str, object], output_dir: Path) -> None:
    username = payload.get("target_profile")
    if not isinstance(username, str):
        return
    write_json_line(
        output_dir / "users.ndjson",
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


def _resolve_targets(mode: str, kwargs: dict[str, object]) -> list[TargetRecord]:
    targets: list[TargetRecord]
    if mode == "profile":
        targets = ProfileScrapeProvider.resolve_targets(
            username=str(kwargs["username"]),
        )
    elif mode == "url":
        targets = UrlScrapeProvider.resolve_targets(post_url=str(kwargs["post_url"]))
    elif mode == "urls":
        targets = UrlScrapeProvider.resolve_targets(
            input_path=_path_arg(kwargs, "input_path"),
        )
    elif mode == "hashtag":
        targets = HashtagScrapeProvider.resolve_targets(
            hashtag=str(kwargs["hashtag"]),
            limit=_optional_int(kwargs.get("limit")),
        )
    elif mode == "location":
        targets = LocationScrapeProvider.resolve_targets(
            location=str(kwargs["location"]),
            limit=_optional_int(kwargs.get("limit")),
        )
    elif mode in {"followers", "following"}:
        targets = FollowGraphProvider.resolve_targets(
            mode=mode,
            username=str(kwargs["username"]),
            limit=_optional_int(kwargs.get("limit")),
        )
    elif mode == "likers":
        targets = LikersProvider.resolve_targets(
            username=str(kwargs["username"]),
            posts_limit=_optional_int(kwargs.get("posts_limit")),
            limit=_optional_int(kwargs.get("limit")),
        )
    elif mode == "commenters":
        targets = CommentersProvider.resolve_targets(
            username=str(kwargs["username"]),
            posts_limit=_optional_int(kwargs.get("posts_limit")),
            limit=_optional_int(kwargs.get("limit")),
        )
    elif mode == "stories":
        targets = StoriesProvider.resolve_targets(
            username=_optional_str(kwargs.get("username")),
            hashtag=_optional_str(kwargs.get("hashtag")),
            limit=_optional_int(kwargs.get("limit")),
        )
    else:
        message = f"Unsupported mode: {mode}"
        raise ValueError(message)
    return targets


def _run_mode(mode: str, kwargs: dict[str, object]) -> RunSummary:
    summary: RunSummary
    if mode == "profile":
        summary = ProfileScrapeProvider.run(
            username=str(kwargs["username"]),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "url":
        summary = UrlScrapeProvider.run(
            post_url=str(kwargs["post_url"]),
            output_dir=_path_arg(kwargs, "output_dir"),
            cookie_header=_optional_str(kwargs.get("cookie_header")) or "",
        )
    elif mode == "urls":
        summary = UrlScrapeProvider.run_urls(
            input_path=_path_arg(kwargs, "input_path"),
            output_dir=_path_arg(kwargs, "output_dir"),
            cookie_header=_optional_str(kwargs.get("cookie_header")) or "",
            resume=bool(kwargs.get("resume")),
            reset_output=bool(kwargs.get("reset_output")),
        )
    elif mode == "hashtag":
        summary = HashtagScrapeProvider.run(
            hashtag=str(kwargs["hashtag"]),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "location":
        summary = LocationScrapeProvider.run(
            location=str(kwargs["location"]),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode in {"followers", "following"}:
        summary = FollowGraphProvider.run(
            mode=mode,
            username=str(kwargs["username"]),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "likers":
        summary = LikersProvider.run(
            username=str(kwargs["username"]),
            posts_limit=_optional_int(kwargs.get("posts_limit")),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "commenters":
        summary = CommentersProvider.run(
            username=str(kwargs["username"]),
            posts_limit=_optional_int(kwargs.get("posts_limit")),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    elif mode == "stories":
        summary = StoriesProvider.run(
            username=_optional_str(kwargs.get("username")),
            hashtag=_optional_str(kwargs.get("hashtag")),
            limit=_optional_int(kwargs.get("limit")),
            output_dir=_path_arg(kwargs, "output_dir"),
        )
    else:
        message = f"Unsupported mode: {mode}"
        raise ValueError(message)
    return summary


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _path_arg(kwargs: dict[str, object], key: str) -> Path:
    value = kwargs.get(key)
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    message = f"Expected path-like value for {key}"
    raise TypeError(message)
