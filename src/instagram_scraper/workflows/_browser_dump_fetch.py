# Copyright (c) 2026
"""Network fetch helpers for browser_dump workflow."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from instagram_scraper.infrastructure.instagram_http import (
    RetryConfig,
    build_instagram_session,
    format_json_error,
    get_json_payload,
    randomized_delay,
    request_with_retry,
)
from instagram_scraper.workflows._browser_dump_io import (
    _optional_int,
    _optional_str,
)

if TYPE_CHECKING:
    import requests

    from instagram_scraper.workflows._browser_dump_types import Config, _CommentRow


def fetch_media_id(
    session: requests.Session,
    post_url: str,
    shortcode: str,
    cfg: Config,
) -> tuple[str | None, str | None]:
    """Resolve a media id from the shortcode API or fallback page HTML.

    Returns
    -------
        A tuple of `(media_id, error)` where exactly one value is usually set.
    """
    shortcode_info_url = (
        f"https://www.instagram.com/api/v1/media/shortcode/{shortcode}/info/"
    )
    response, error = _request_with_retry(session, shortcode_info_url, cfg)
    if response is not None:
        payload = get_json_payload(response)
        if payload is not None:
            items = payload.get("items")
            if isinstance(items, list) and items:
                first = items[0]
                if isinstance(first, dict):
                    media_id = cast("dict[str, object]", first).get("id")
                    if media_id is not None:
                        return str(media_id), None

    response, error = _request_with_retry(session, post_url, cfg)
    if response is None:
        return None, error or "media_page_request_failed"
    return _extract_media_id_from_html(response.text, shortcode)


def _fetch_media_info(
    session: requests.Session,
    media_id: str,
    cfg: Config,
) -> tuple[dict[str, object] | None, str | None]:
    response, error = _request_with_retry(
        session,
        f"https://www.instagram.com/api/v1/media/{media_id}/info/",
        cfg,
    )
    if response is None:
        return None, error or "media_info_request_failed"
    payload = get_json_payload(response)
    if payload is None:
        return None, format_json_error(response, "media_info")
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
        params = {"can_support_threading": "true", "permalink_enabled": "false"}
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
        payload = get_json_payload(response)
        if payload is None:
            return comments, format_json_error(response, "comments")
        page_comments = payload.get("comments")
        if isinstance(page_comments, list):
            comments.extend(_comment_rows(cast("list[object]", page_comments)))
        has_more = bool(payload.get("has_more_comments"))
        next_cursor = payload.get("next_max_id") or payload.get("next_min_id")
        if not has_more or not isinstance(next_cursor, str):
            return comments, None
        max_id = next_cursor
        randomized_delay(cfg.min_delay, cfg.max_delay, scale=1.5)
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


def _build_session(cookie_header: str) -> requests.Session:
    return build_instagram_session(cookie_header)


def _randomized_delay(
    min_delay: float,
    max_delay: float,
    *,
    extra_scale: float = 1.0,
) -> None:
    randomized_delay(min_delay, max_delay, scale=extra_scale)


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
    match = re.search(r"/(?:p|reel)/([^/]+)/?$", url)
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
