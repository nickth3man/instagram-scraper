# Copyright (c) 2026
"""Shared fixtures and constants for CLI tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Generator


runner = CliRunner()

DEFAULT_SHARED_OPTIONS = {
    "raw_captures": False,
    "request_timeout": 30,
    "max_retries": 5,
    "checkpoint_every": 20,
}


@pytest.fixture
def mock_pipeline() -> Generator[MagicMock]:
    """Mock the run_pipeline function."""
    with patch("instagram_scraper.cli.run_pipeline") as mock:
        mock.return_value = 0
        yield mock


@pytest.fixture
def mock_context(mocker) -> MagicMock:
    """Create a mock Typer context."""
    ctx = mocker.MagicMock()
    ctx.obj = {}
    return ctx


@pytest.fixture(autouse=True)
def clear_cookie_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep local .env cookie values from leaking into unrelated CLI tests."""
    monkeypatch.delenv("IG_COOKIE_HEADER", raising=False)


@pytest.fixture
def mock_post(mocker) -> MagicMock:
    post = mocker.MagicMock()
    post.shortcode = "ABC123"
    post.date_utc = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    post.caption = "Test caption"
    post.likes = 100
    post.comments = 5
    post.is_video = True
    post.typename = "GraphVideo"
    post.get_comments.return_value = []
    return post


@pytest.fixture
def mock_comment(mocker) -> MagicMock:
    comment = mocker.MagicMock()
    comment.id = 12345
    comment.text = "Test comment text"
    comment.created_at_utc = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)
    comment.likes_count = 10

    owner = mocker.MagicMock()
    owner.username = "commenter_user"
    owner.userid = 67890
    comment.owner = owner

    comment.answers = []
    return comment


@pytest.fixture
def mock_reply(mocker) -> MagicMock:
    reply = mocker.MagicMock()
    reply.id = 12346
    reply.text = "Reply text"
    reply.created_at_utc = datetime(2024, 1, 15, 11, 5, 0, tzinfo=UTC)
    reply.likes_count = 3

    owner = mocker.MagicMock()
    owner.username = "replier_user"
    owner.userid = 67891
    reply.owner = owner

    return reply


@pytest.fixture
def mock_profile(mocker, mock_post) -> MagicMock:
    profile = mocker.MagicMock()
    profile.get_posts.return_value = [mock_post]
    return profile


@pytest.fixture
def mock_instaloader(mocker) -> MagicMock:
    loader = mocker.MagicMock()
    loader.context = mocker.MagicMock()
    loader.context.quotamessages = None
    return loader
