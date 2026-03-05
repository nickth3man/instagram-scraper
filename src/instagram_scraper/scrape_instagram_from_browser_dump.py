# Copyright (c) 2026
"""Scrape Instagram post metadata and comments from a browser-tool URL dump."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Generator

    import requests

from ._instagram_http import (
    RetryConfig,
    build_instagram_session,
    json_error,
    json_payload,
    randomized_delay,
    request_with_retry,
)
from ._shared_io import (
    append_csv_row,
    atomic_write_text,
    ensure_csv_with_header,
    load_json_dict,
    write_json_line,
)

DEFAULT_DATA_DIR_FALLBACK = "data"
DEFAULT_USERNAME_FALLBACK = "target_profile"


class _CheckpointState(TypedDict):
    started_at_utc: str
    updated_at_utc: str
    next_index: int
    processed: int
    posts: int
    comments: int
    errors: int
    total_urls: int
    completed: NotRequired[bool]


class _PostRow(TypedDict):
    media_id: str
    shortcode: str
    post_url: str
    type: int | None
    taken_at_utc: int | None
    caption: str | None
    like_count: int | None
    comment_count: int | None


class _CommentRow(TypedDict):
    id: str
    created_at_utc: int | None
    text: str | None
    comment_like_count: int | None
    owner_username: str | None
    owner_id: str


class _ErrorRow(TypedDict):
    index: int
    post_url: str
    shortcode: str | None
    media_id: str | None
    stage: str
    error: str


class _OutputPaths(TypedDict):
    posts_ndjson: Path
    comments_ndjson: Path
    errors_ndjson: Path
    posts_csv: Path
    comments_csv: Path
    errors_csv: Path


class _RunMetrics(TypedDict):
    start_index: int
    end_index: int
    started_at_utc: str
    processed: int
    posts: int
    comments: int
    errors: int


@dataclass
class _RunContext:
    cfg: Config
    session: requests.Session
    output_paths: _OutputPaths
    headers: dict[str, list[str]]
    total_urls: int
    metrics: _RunMetrics


@dataclass(frozen=True)
class Config:
    """Runtime configuration for scraping browser-dump URLs."""

    tool_dump_path: Path
    output_dir: Path
    resume: bool
    reset_output: bool
    start_index: int
    limit: int | None
    checkpoint_every: int
    max_comment_pages: int
    min_delay: float
    max_delay: float
    request_timeout: int
    max_retries: int
    base_retry_seconds: float
    cookie_header: str


def parse_args() -> Config:
    """Parse CLI arguments into a validated configuration object.

    Returns
    -------
    Config
        The normalized runtime configuration for the scraper.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool-dump-path", default=str(_default_tool_dump_path()))
    parser.add_argument("--output-dir", default=str(_default_output_dir()))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--max-comment-pages", type=int, default=100)
    parser.add_argument("--min-delay", type=float, default=0.05)
    parser.add_argument("--max-delay", type=float, default=0.2)
    parser.add_argument("--request-timeout", type=int, default=30)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--base-retry-seconds", type=float, default=2.0)
    parser.add_argument("--cookie-header", default=os.getenv("IG_COOKIE_HEADER", ""))
    args = parser.parse_args()
    return Config(
        tool_dump_path=Path(args.tool_dump_path),
        output_dir=Path(args.output_dir),
        resume=args.resume,
        reset_output=args.reset_output,
        start_index=max(0, args.start_index),
        limit=args.limit,
        checkpoint_every=max(1, args.checkpoint_every),
        max_comment_pages=max(1, args.max_comment_pages),
        min_delay=max(0.0, args.min_delay),
        max_delay=max(args.min_delay, args.max_delay),
        request_timeout=max(1, args.request_timeout),
        max_retries=max(1, args.max_retries),
        base_retry_seconds=max(0.1, args.base_retry_seconds),
        cookie_header=args.cookie_header,
    )


def fetch_media_id(
    session: requests.Session,
    post_url: str,
    shortcode: str,
    cfg: Config,
) -> tuple[str | None, str | None]:
    """Resolve an Instagram media id from a shortcode or fallback page HTML.

    Returns
    -------
    tuple[str | None, str | None]
        The resolved media id and any resulting error code.

    """
    shortcode_info_url = (
        f"https://www.instagram.com/api/v1/media/shortcode/{shortcode}/info/"
    )
    # Try the clean API route first because it gives us structured JSON.
    response, error = _request_with_retry(session, shortcode_info_url, cfg)
    if response is not None:
        payload = _json_payload(response)
        if payload is not None:
            items = payload.get("items")
            if isinstance(items, list) and items:
                first = items[0]
                if isinstance(first, dict):
                    media_id = cast("dict[str, object]", first).get("id")
                    if media_id is not None:
                        return str(media_id), None

    # If the API route fails, fall back to scraping the public page HTML.
    response, error = _request_with_retry(session, post_url, cfg)
    if response is None:
        return None, error or "media_page_request_failed"
    return _extract_media_id_from_html(response.text, shortcode)


def run(cfg: Config) -> dict[str, object]:
    """Scrape all URLs from the tool dump and persist the generated artifacts.

    Returns
    -------
    dict[str, object]
        Summary metadata for the completed scrape.

    """
    # Read every target URL up front so the rest of the run can work with a
    # simple list and known total size.
    urls = _load_urls_from_tool_dump(cfg.tool_dump_path)
    output_paths = _prepare_output(cfg)
    post_header = [
        "media_id",
        "shortcode",
        "post_url",
        "type",
        "taken_at_utc",
        "caption",
        "like_count",
        "comment_count",
    ]
    comment_header = [
        "media_id",
        "shortcode",
        "post_url",
        "id",
        "created_at_utc",
        "text",
        "comment_like_count",
        "owner_username",
        "owner_id",
    ]
    error_header = ["index", "post_url", "shortcode", "media_id", "stage", "error"]
    _ensure_csv_with_header(
        output_paths["posts_csv"],
        post_header,
        reset=cfg.reset_output,
    )
    _ensure_csv_with_header(
        output_paths["comments_csv"],
        comment_header,
        reset=cfg.reset_output,
    )
    _ensure_csv_with_header(
        output_paths["errors_csv"],
        error_header,
        reset=cfg.reset_output,
    )

    # Resuming means "start from the saved checkpoint if there is one".
    checkpoint = _load_checkpoint(cfg.output_dir) if cfg.resume else None
    metrics = _initial_metrics(cfg, urls, checkpoint)
    session = _build_session(cfg.cookie_header)
    context = _RunContext(
        cfg=cfg,
        session=session,
        output_paths=output_paths,
        headers={
            "posts": post_header,
            "comments": comment_header,
            "errors": error_header,
        },
        total_urls=len(urls),
        metrics=metrics,
    )
    try:
        for index in range(metrics["start_index"], metrics["end_index"]):
            _process_url(context, index, urls[index])
    finally:
        session.close()
    summary = _build_summary(cfg.output_dir, output_paths, metrics)
    _atomic_write_text(
        cfg.output_dir / "summary.json",
        json.dumps(summary, indent=2),
    )
    _save_checkpoint(
        cfg.output_dir,
        _checkpoint_state(metrics, len(urls), completed=True),
    )
    return summary


def run_url_scrape(
    *,
    urls: list[str],
    output_dir: Path,
    cookie_header: str,
    resume: bool = False,
    reset_output: bool = False,
) -> dict[str, object]:
    """Run the browser-dump scraper for an explicit list of post URLs.

    Returns
    -------
    dict[str, object]
        Summary metadata for the completed scrape.

    """
    output_dir.mkdir(parents=True, exist_ok=True)
    tool_dump_path = output_dir / "tool_dump.json"
    tool_dump_path.write_text(
        json.dumps({"count": len(urls), "urls": urls}, indent=2),
        encoding="utf-8",
    )
    return run(
        Config(
            tool_dump_path=tool_dump_path,
            output_dir=output_dir,
            resume=resume,
            reset_output=reset_output,
            start_index=0,
            limit=None,
            checkpoint_every=20,
            max_comment_pages=100,
            min_delay=0.05,
            max_delay=0.2,
            request_timeout=30,
            max_retries=5,
            base_retry_seconds=2.0,
            cookie_header=cookie_header,
        ),
    )


def main() -> None:
    """Run the browser-dump scraper and emit the final summary as JSON."""
    summary = run(parse_args())
    sys.stdout.write(json.dumps(summary) + "\n")


def _default_data_dir() -> Path:
    return Path(os.getenv("INSTAGRAM_DATA_DIR", DEFAULT_DATA_DIR_FALLBACK))


def _default_username() -> str:
    return os.getenv("INSTAGRAM_USERNAME", DEFAULT_USERNAME_FALLBACK)


def _default_tool_dump_path() -> Path:
    return _default_data_dir() / "tool_dump.json"


def _default_output_dir() -> Path:
    return _default_data_dir() / _default_username()


def _iso_utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _load_urls_from_tool_dump(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    for payload in _tool_dump_payloads(text):
        urls = payload.get("urls")
        if isinstance(urls, list) and all(isinstance(url, str) for url in urls):
            return [url for url in urls if isinstance(url, str)]
    message = "Could not parse URL payload from tool dump"
    raise ValueError(message)


def _tool_dump_payloads(text: str) -> Generator[dict[str, object]]:
    # Browser-tool dumps are not always "just JSON". This helper tries the plain
    # JSON shape first, then a fenced ```json block if the dump was pasted from chat.
    start = text.find('{"count"')
    end = text.rfind("}")
    if start != -1 and end > start:
        raw_payload = json.loads(text[start : end + 1])
        if isinstance(raw_payload, dict):
            yield cast("dict[str, object]", raw_payload)
    fenced_start = text.find("```json")
    fenced_end = text.rfind("```")
    if fenced_start != -1 and fenced_end > fenced_start:
        raw_payload = json.loads(
            text[fenced_start + len("```json") : fenced_end].strip(),
        )
        if isinstance(raw_payload, dict):
            yield cast("dict[str, object]", raw_payload)


def _build_session(cookie_header: str) -> requests.Session:
    return build_instagram_session(cookie_header)


def _randomized_delay(cfg: Config, *, extra_scale: float = 1.0) -> None:
    randomized_delay(cfg.min_delay, cfg.max_delay, scale=extra_scale)


def _request_with_retry(
    session: requests.Session,
    url: str,
    cfg: Config,
    *,
    params: dict[str, str] | None = None,
) -> tuple[requests.Response | None, str | None]:
    return request_with_retry(
        session,
        url,
        RetryConfig(
            timeout=cfg.request_timeout,
            max_retries=cfg.max_retries,
            min_delay=cfg.min_delay,
            max_delay=cfg.max_delay,
            base_retry_seconds=cfg.base_retry_seconds,
        ),
        params=params,
    )


def _extract_shortcode(url: str) -> str | None:
    match = re.search(r"/(?:p|reel)/([^/]+)/", url)
    return None if match is None else match.group(1)


def _extract_media_id_from_html(
    html: str,
    shortcode: str,
) -> tuple[str | None, str | None]:
    primary = re.search(r'"media_id":"(\d+)"', html)
    if primary is not None:
        return primary.group(1), None
    escaped_shortcode = re.escape(shortcode)
    secondary = re.search(
        rf'"shortcode":"{escaped_shortcode}".*?"id":"(\d+)"',
        html,
        re.DOTALL,
    )
    if secondary is None:
        return None, "media_id_not_found"
    return secondary.group(1), None


def _fetch_media_info(
    session: requests.Session,
    media_id: str,
    cfg: Config,
) -> tuple[dict[str, object] | None, str | None]:
    url = f"https://www.instagram.com/api/v1/media/{media_id}/info/"
    response, error = _request_with_retry(session, url, cfg)
    if response is None:
        return None, error or "media_info_request_failed"
    payload = _json_payload(response)
    if payload is None:
        return None, _json_error(response, "media_info")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None, "media_info_empty"
    first = items[0]
    if not isinstance(first, dict):
        return None, "media_info_invalid"
    return cast("dict[str, object]", first), None


def _fetch_comments(
    session: requests.Session,
    media_id: str,
    cfg: Config,
) -> tuple[list[_CommentRow], str | None]:
    comments: list[_CommentRow] = []
    max_id: str | None = None
    for _ in range(cfg.max_comment_pages):
        # Instagram returns comments in pages. `max_id` asks for the next page.
        params = {
            "can_support_threading": "true",
            "permalink_enabled": "false",
        }
        if max_id is not None:
            params["max_id"] = max_id
        response, error = _request_with_retry(
            session,
            f"https://www.instagram.com/api/v1/media/{media_id}/comments/",
            cfg,
            params=params,
        )
        if response is None:
            return comments, error or "comments_request_failed"
        payload = _json_payload(response)
        if payload is None:
            return comments, _json_error(response, "comments")
        page_comments = payload.get("comments")
        if isinstance(page_comments, list):
            comments.extend(_comment_rows(cast("list[object]", page_comments)))
        has_more = bool(payload.get("has_more_comments"))
        next_cursor = payload.get("next_max_id") or payload.get("next_min_id")
        if not has_more or not isinstance(next_cursor, str):
            return comments, None
        max_id = next_cursor
        # Slow down slightly between pages to reduce the chance of rate limiting.
        _randomized_delay(cfg, extra_scale=1.5)
    return comments, "comments_page_guard_exhausted"


def _comment_rows(comments: list[object]) -> list[_CommentRow]:
    rows: list[_CommentRow] = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        comment_dict = cast("dict[str, object]", comment)
        user = comment_dict.get("user")
        if not isinstance(user, dict):
            user = {}
        user_dict = cast("dict[str, object]", user)
        # Normalize each API comment into the small shape the rest of this repo uses.
        rows.append(
            {
                "id": str(comment_dict.get("pk") or ""),
                "created_at_utc": _optional_int(comment_dict.get("created_at_utc")),
                "text": _optional_str(comment_dict.get("text")),
                "comment_like_count": _optional_int(
                    comment_dict.get("comment_like_count"),
                ),
                "owner_username": _optional_str(user_dict.get("username")),
                "owner_id": str(user_dict.get("pk") or ""),
            },
        )
    return rows


def _atomic_write_text(path: Path, content: str) -> None:
    atomic_write_text(path, content)


def _write_json_line(path: Path, payload: dict[str, object]) -> None:
    write_json_line(path, payload)


def _ensure_csv_with_header(path: Path, header: list[str], *, reset: bool) -> None:
    ensure_csv_with_header(path, header, reset=reset)


def _append_csv_row(path: Path, header: list[str], row: dict[str, object]) -> None:
    append_csv_row(path, header, row)


def _checkpoint_path(output_dir: Path) -> Path:
    return output_dir / "checkpoint.json"


def _load_checkpoint(output_dir: Path) -> _CheckpointState | None:
    path = _checkpoint_path(output_dir)
    payload = load_json_dict(path)
    return cast("_CheckpointState", payload) if payload is not None else None


def _save_checkpoint(output_dir: Path, state: _CheckpointState) -> None:
    _atomic_write_text(_checkpoint_path(output_dir), json.dumps(state, indent=2))


def _prepare_output(cfg: Config) -> _OutputPaths:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    if cfg.reset_output:
        # Reset mode throws away old artifacts so the next run starts cleanly.
        for name in (
            "posts.ndjson",
            "comments.ndjson",
            "errors.ndjson",
            "posts.csv",
            "comments.csv",
            "errors.csv",
            "summary.json",
            "checkpoint.json",
        ):
            path = cfg.output_dir / name
            if path.exists():
                path.unlink()
    return {
        "posts_ndjson": cfg.output_dir / "posts.ndjson",
        "comments_ndjson": cfg.output_dir / "comments.ndjson",
        "errors_ndjson": cfg.output_dir / "errors.ndjson",
        "posts_csv": cfg.output_dir / "posts.csv",
        "comments_csv": cfg.output_dir / "comments.csv",
        "errors_csv": cfg.output_dir / "errors.csv",
    }


def _initial_metrics(
    cfg: Config,
    urls: list[str],
    checkpoint: _CheckpointState | None,
) -> _RunMetrics:
    start_index = cfg.start_index
    if checkpoint is not None:
        # On resume, never go backwards earlier than the saved next index.
        start_index = max(start_index, checkpoint["next_index"])
    end_index = (
        len(urls)
        if cfg.limit is None
        else min(len(urls), start_index + cfg.limit)
    )
    started_at = checkpoint["started_at_utc"] if checkpoint else _iso_utc_now()
    return {
        "start_index": start_index,
        "end_index": end_index,
        "started_at_utc": started_at,
        "processed": checkpoint["processed"] if checkpoint else 0,
        "posts": checkpoint["posts"] if checkpoint else 0,
        "comments": checkpoint["comments"] if checkpoint else 0,
        "errors": checkpoint["errors"] if checkpoint else 0,
    }


def _process_url(context: _RunContext, index: int, post_url: str) -> None:
    shortcode = _extract_shortcode(post_url)
    if shortcode is None:
        # Save progress even for bad input so a rerun does not get stuck on the
        # same broken row forever.
        error_row: _ErrorRow = {
            "index": index,
            "post_url": post_url,
            "shortcode": None,
            "media_id": None,
            "stage": "extract_shortcode",
            "error": "missing_shortcode",
        }
        _record_error(error_row, context.output_paths, context.headers["errors"])
        _increment_metric(context.metrics, "errors")
        _increment_metric(context.metrics, "processed")
        _save_checkpoint(
            context.cfg.output_dir,
            _checkpoint_state(
                context.metrics,
                context.total_urls,
                next_index=index + 1,
            ),
        )
        return
    media_id, media_id_error = fetch_media_id(
        context.session,
        post_url,
        shortcode,
        context.cfg,
    )
    if media_id is None:
        error_row: _ErrorRow = {
            "index": index,
            "post_url": post_url,
            "shortcode": shortcode,
            "media_id": None,
            "stage": "fetch_media_id",
            "error": media_id_error or "media_id_not_found",
        }
        _record_error(error_row, context.output_paths, context.headers["errors"])
        _increment_metric(context.metrics, "errors")
        _increment_metric(context.metrics, "processed")
        _save_checkpoint(
            context.cfg.output_dir,
            _checkpoint_state(
                context.metrics,
                context.total_urls,
                next_index=index + 1,
            ),
        )
        _randomized_delay(context.cfg)
        return
    _process_media(context, index, post_url, shortcode, media_id)
    _increment_metric(context.metrics, "processed")
    if context.metrics["processed"] % context.cfg.checkpoint_every == 0:
        # Periodic checkpoints make long runs resumable after crashes or rate limits.
        _save_checkpoint(
            context.cfg.output_dir,
            _checkpoint_state(
                context.metrics,
                context.total_urls,
                next_index=index + 1,
            ),
        )
    _randomized_delay(context.cfg)


def _process_media(
    context: _RunContext,
    index: int,
    post_url: str,
    shortcode: str,
    media_id: str,
) -> None:
    media_info, media_info_error = _fetch_media_info(
        context.session,
        media_id,
        context.cfg,
    )
    if media_info is None:
        error_row: _ErrorRow = {
            "index": index,
            "post_url": post_url,
            "shortcode": shortcode,
            "media_id": media_id,
            "stage": "fetch_media_info",
            "error": media_info_error or "media_info_failed",
        }
        _record_error(error_row, context.output_paths, context.headers["errors"])
        _increment_metric(context.metrics, "errors")
        _save_checkpoint(
            context.cfg.output_dir,
            _checkpoint_state(
                context.metrics,
                context.total_urls,
                next_index=index + 1,
            ),
        )
        _randomized_delay(context.cfg)
        return
    post_row = _post_row(media_id, shortcode, post_url, media_info)
    post_payload = _post_payload(post_row)
    # Write each record immediately so progress is durable even in long scrapes.
    _write_json_line(context.output_paths["posts_ndjson"], post_payload)
    _append_csv_row(
        context.output_paths["posts_csv"],
        context.headers["posts"],
        post_payload,
    )
    _increment_metric(context.metrics, "posts")
    comments_error = _write_comments(context, media_id, shortcode, post_url, post_row)
    if comments_error is not None:
        error_row: _ErrorRow = {
            "index": index,
            "post_url": post_url,
            "shortcode": shortcode,
            "media_id": media_id,
            "stage": "fetch_comments",
            "error": comments_error,
        }
        _record_error(error_row, context.output_paths, context.headers["errors"])
        _increment_metric(context.metrics, "errors")


def _write_comments(
    context: _RunContext,
    media_id: str,
    shortcode: str,
    post_url: str,
    post_row: _PostRow,
) -> str | None:
    declared_comment_count = post_row["comment_count"]
    if declared_comment_count is None or declared_comment_count <= 0:
        # Skip the network call when Instagram already says there are no comments.
        return None
    post_comments, comments_error = _fetch_comments(
        context.session,
        media_id,
        context.cfg,
    )
    for comment in post_comments:
        row = {
            "media_id": media_id,
            "shortcode": shortcode,
            "post_url": post_url,
            **comment,
        }
        _write_json_line(context.output_paths["comments_ndjson"], row)
        _append_csv_row(
            context.output_paths["comments_csv"],
            context.headers["comments"],
            row,
        )
        _increment_metric(context.metrics, "comments")
    return comments_error


def _post_row(
    media_id: str,
    shortcode: str,
    post_url: str,
    media_info: dict[str, object],
) -> _PostRow:
    caption = media_info.get("caption")
    caption_text: str | None = None
    if isinstance(caption, dict):
        caption_text = _optional_str(cast("dict[str, object]", caption).get("text"))
    return {
        "media_id": media_id,
        "shortcode": shortcode,
        "post_url": post_url,
        "type": _optional_int(media_info.get("media_type")),
        "taken_at_utc": _optional_int(media_info.get("taken_at_utc")),
        "caption": caption_text,
        "like_count": _optional_int(media_info.get("like_count")),
        "comment_count": _optional_int(media_info.get("comment_count")),
    }


def _record_error(
    error_row: _ErrorRow,
    output_paths: _OutputPaths,
    error_header: list[str],
) -> None:
    error_payload = dict(error_row)
    _write_json_line(output_paths["errors_ndjson"], error_payload)
    _append_csv_row(output_paths["errors_csv"], error_header, error_payload)


def _checkpoint_state(
    metrics: _RunMetrics,
    total_urls: int,
    *,
    next_index: int | None = None,
    completed: bool | None = None,
) -> _CheckpointState:
    # The checkpoint is the minimal state needed to resume later.
    state: _CheckpointState = {
        "started_at_utc": metrics["started_at_utc"],
        "updated_at_utc": _iso_utc_now(),
        "next_index": metrics["end_index"] if next_index is None else next_index,
        "processed": metrics["processed"],
        "posts": metrics["posts"],
        "comments": metrics["comments"],
        "errors": metrics["errors"],
        "total_urls": total_urls,
    }
    if completed is not None:
        state["completed"] = completed
    return state


def _build_summary(
    output_dir: Path,
    output_paths: _OutputPaths,
    metrics: _RunMetrics,
) -> dict[str, object]:
    username = output_dir.name or "unknown"
    # The summary points at every artifact so humans and automation can discover
    # the outputs without scanning the whole folder.
    return {
        "target_profile": username,
        "source_url": (
            f"https://www.instagram.com/{username}/?hl=en"
            if username != "unknown"
            else None
        ),
        "started_at_utc": metrics["started_at_utc"],
        "finished_at_utc": _iso_utc_now(),
        "range": {
            "start_index": metrics["start_index"],
            "end_index_exclusive": metrics["end_index"],
        },
        "processed": metrics["processed"],
        "posts": metrics["posts"],
        "comments": metrics["comments"],
        "errors": metrics["errors"],
        "files": {
            "posts_csv": str(output_paths["posts_csv"]),
            "comments_csv": str(output_paths["comments_csv"]),
            "errors_csv": str(output_paths["errors_csv"]),
            "posts_ndjson": str(output_paths["posts_ndjson"]),
            "comments_ndjson": str(output_paths["comments_ndjson"]),
            "errors_ndjson": str(output_paths["errors_ndjson"]),
            "checkpoint": str(_checkpoint_path(output_dir)),
        },
    }


def _post_payload(post_row: _PostRow) -> dict[str, object]:
    return {
        "media_id": post_row["media_id"],
        "shortcode": post_row["shortcode"],
        "post_url": post_row["post_url"],
        "type": post_row["type"],
        "taken_at_utc": post_row["taken_at_utc"],
        "caption": post_row["caption"],
        "like_count": post_row["like_count"],
        "comment_count": post_row["comment_count"],
    }


def _json_payload(response: requests.Response) -> dict[str, object] | None:
    return json_payload(response)


def _json_error(response: requests.Response, prefix: str) -> str:
    return json_error(response, prefix)


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _increment_metric(
    metrics: _RunMetrics,
    key: Literal["processed", "posts", "comments", "errors"],
) -> None:
    metrics[key] += 1


if __name__ == "__main__":
    main()
