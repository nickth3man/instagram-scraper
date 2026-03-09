# Copyright (c) 2026
"""Async helpers for fetching and normalizing Instagram comment pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from ._async_http import async_json_payload, async_request_with_retry
from .config import RetryConfig


class _ResponseReleaser(Protocol):
    async def release(self) -> object: ...


@dataclass(frozen=True, slots=True)
class CommentRow:
    """Normalized comment row for async comment fetches."""

    id: str
    media_id: str
    shortcode: str | None
    text: str | None
    created_at_utc: int | None
    owner_username: str | None
    owner_id: str | None
    comment_like_count: int


@dataclass(frozen=True, slots=True)
class CommentBatch:
    """A single page of normalized comments plus pagination state."""

    media_id: str
    comments: list[CommentRow]
    has_more: bool
    next_cursor: str | None


def _comment_row_from_payload(media_id: str, item: dict[str, object]) -> CommentRow:
    owner = item.get("owner")
    owner_dict = cast("dict[str, object]", owner) if isinstance(owner, dict) else {}
    comment_like_count = item.get("comment_like_count")
    if comment_like_count is None:
        comment_like_count = item.get("like_count")

    shortcode = item.get("shortcode")
    text = item.get("text")
    created_at_utc = item.get("created_at_utc")
    owner_username = owner_dict.get("username")
    owner_id = owner_dict.get("id")

    return CommentRow(
        id=str(item.get("id") or ""),
        media_id=media_id,
        shortcode=shortcode if isinstance(shortcode, str) else None,
        text=text if isinstance(text, str) else None,
        created_at_utc=created_at_utc if isinstance(created_at_utc, int) else None,
        owner_username=owner_username if isinstance(owner_username, str) else None,
        owner_id=str(owner_id) if owner_id is not None else None,
        comment_like_count=(
            comment_like_count if isinstance(comment_like_count, int) else 0
        ),
    )


async def fetch_comments_page(
    session: object,
    media_id: str,
    page_cursor: str | None = None,
) -> CommentBatch | None:
    """Fetch one page of comments using the shared async retry helper.

    Returns
    -------
    CommentBatch | None
        The normalized comment page, or `None` when the request or payload fails.

    """
    params: dict[str, str] = {"media_id": media_id}
    if page_cursor:
        params["cursor"] = page_cursor

    response, error = await async_request_with_retry(
        session,
        "/comments",
        RetryConfig(
            timeout=30,
            max_retries=3,
            min_delay=1.0,
            max_delay=5.0,
            base_retry_seconds=1.0,
        ),
        params=params,
    )
    if error is not None or response is None:
        return None

    try:
        payload = await async_json_payload(response)
    finally:
        await cast("_ResponseReleaser", response).release()

    if payload is None:
        return None

    data = payload.get("data")
    if not isinstance(data, list):
        return None

    comments: list[CommentRow] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        comments.append(
            _comment_row_from_payload(media_id, cast("dict[str, object]", item)),
        )

    next_cursor = payload.get("next_cursor")
    return CommentBatch(
        media_id=media_id,
        comments=comments,
        has_more=bool(payload.get("has_more", False)),
        next_cursor=next_cursor if isinstance(next_cursor, str) else None,
    )
