from unittest.mock import AsyncMock

import pytest

from instagram_scraper import async_comments
from instagram_scraper.async_comments import (
    CommentBatch,
    CommentRow,
    fetch_comments_page,
)


def test_comment_row_creation() -> None:
    row = CommentRow(
        id="c1",
        media_id="m1",
        shortcode="sc1",
        text="hello",
        created_at_utc=1234567890,
        owner_username="user1",
        owner_id="owner1",
        comment_like_count=5,
    )
    assert row.id == "c1"
    assert row.media_id == "m1"
    assert row.shortcode == "sc1"
    assert row.text == "hello"
    assert row.created_at_utc == 1234567890
    assert row.owner_username == "user1"
    assert row.owner_id == "owner1"
    assert row.comment_like_count == 5


def test_comment_batch_creation() -> None:
    sample_row = CommentRow(
        id="c1",
        media_id="m1",
        shortcode="sc1",
        text="hi",
        created_at_utc=1,
        owner_username="user1",
        owner_id="owner1",
        comment_like_count=1,
    )
    batch = CommentBatch(
        media_id="m1",
        comments=[sample_row],
        has_more=False,
        next_cursor=None,
    )
    assert batch.media_id == "m1"
    assert batch.has_more is False
    assert batch.next_cursor is None
    assert len(batch.comments) == 1


class _DummyResponse:
    def __init__(self) -> None:
        self.release = AsyncMock()


@pytest.mark.asyncio
async def test_fetch_comments_page_parses_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _DummyResponse()

    async_request = AsyncMock(return_value=(response, None))
    json_payload = AsyncMock(
        return_value={
            "data": [
                {
                    "id": "c1",
                    "shortcode": "SC1",
                    "text": "hello",
                    "created_at_utc": 123,
                    "comment_like_count": 4,
                    "owner": {"username": "alice", "id": "42"},
                },
            ],
            "has_more": True,
            "next_cursor": "cursor-2",
        },
    )
    monkeypatch.setattr(async_comments, "async_request_with_retry", async_request)
    monkeypatch.setattr(async_comments, "async_json_payload", json_payload)

    batch = await fetch_comments_page(object(), "media-1", page_cursor="cursor-1")

    assert batch == CommentBatch(
        media_id="media-1",
        comments=[
            CommentRow(
                id="c1",
                media_id="media-1",
                shortcode="SC1",
                text="hello",
                created_at_utc=123,
                owner_username="alice",
                owner_id="42",
                comment_like_count=4,
            ),
        ],
        has_more=True,
        next_cursor="cursor-2",
    )
    async_request.assert_awaited_once()
    json_payload.assert_awaited_once_with(response)
    response.release.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_comments_page_returns_none_on_request_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async_request = AsyncMock(return_value=(None, object()))
    monkeypatch.setattr(async_comments, "async_request_with_retry", async_request)

    batch = await fetch_comments_page(object(), "media-1")

    assert batch is None


@pytest.mark.asyncio
async def test_fetch_comments_page_accepts_like_count_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _DummyResponse()
    monkeypatch.setattr(
        async_comments,
        "async_request_with_retry",
        AsyncMock(return_value=(response, None)),
    )
    monkeypatch.setattr(
        async_comments,
        "async_json_payload",
        AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "c2",
                        "like_count": 7,
                        "owner": {"username": "bob", "id": 99},
                    },
                ],
                "has_more": False,
                "next_cursor": None,
            },
        ),
    )

    batch = await fetch_comments_page(object(), "media-2")

    assert batch is not None
    assert batch.comments[0].comment_like_count == 7
    assert batch.comments[0].owner_id == "99"
