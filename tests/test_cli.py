# Copyright (c) 2026
"""Tests for cli module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from instagram_scraper.cli import (
    STORIES_SEED_MESSAGE,
    app,
    configure_scrape,
)

if TYPE_CHECKING:
    from collections.abc import Generator


runner = CliRunner()

DEFAULT_SHARED_OPTIONS = {
    "raw_captures": False,
    "request_timeout": 30,
    "max_retries": 5,
    "checkpoint_every": 20,
}


# Fixtures


@pytest.fixture
def mock_pipeline(mocker) -> Generator[MagicMock]:
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


# Test CLI App Structure


def test_app_has_scrape_subcommand() -> None:
    """Test that app has scrape subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scrape" in result.output


def test_scrape_app_has_subcommands() -> None:
    """Test that scrape subcommand has registered commands."""
    result = runner.invoke(app, ["scrape", "--help"])
    assert result.exit_code == 0
    assert "profile" in result.output
    assert "url" in result.output
    assert "hashtag" in result.output
    assert "location" in result.output
    assert "followers" in result.output
    assert "following" in result.output
    assert "likers" in result.output
    assert "commenters" in result.output
    assert "stories" in result.output


# Test scrape_profile command


def test_scrape_profile_success(mock_pipeline: MagicMock) -> None:
    """Test successful profile scrape command."""
    result = runner.invoke(app, ["scrape", "profile", "--username", "testuser"])

    assert result.exit_code == 0
    expected = {**DEFAULT_SHARED_OPTIONS, "username": "testuser", "output_dir": None}
    mock_pipeline.assert_called_once_with("profile", **expected)


def test_scrape_profile_with_output_dir(
    mock_pipeline: MagicMock, tmp_path: Path,
) -> None:
    """Test profile scrape with output directory."""
    result = runner.invoke(
        app,
        ["scrape", "profile", "--username", "testuser", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "output_dir": tmp_path,
    }
    mock_pipeline.assert_called_once_with("profile", **expected)


def test_scrape_profile_missing_username() -> None:
    """Test profile scrape without required username."""
    result = runner.invoke(app, ["scrape", "profile"])

    assert result.exit_code != 0
    assert "--username" in result.output or "Required" in result.output


# Test scrape_url command


def test_scrape_url_success(mock_pipeline: MagicMock) -> None:
    """Test successful URL scrape command."""
    result = runner.invoke(
        app,
        ["scrape", "url", "--url", "https://www.instagram.com/p/ABC123/"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "post_url": "https://www.instagram.com/p/ABC123/",
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("url", **expected)


def test_scrape_url_with_cookie(mock_pipeline: MagicMock) -> None:
    """Test URL scrape with cookie header."""
    result = runner.invoke(
        app,
        [
            "scrape",
            "url",
            "--url",
            "https://www.instagram.com/p/ABC123/",
            "--cookie-header",
            "sessionid=abc123",
        ],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "post_url": "https://www.instagram.com/p/ABC123/",
        "output_dir": None,
        "cookie_header": "sessionid=abc123",
        "has_auth": True,
    }
    mock_pipeline.assert_called_once_with("url", **expected)


def test_scrape_url_uses_env_cookie_default(mock_pipeline: MagicMock) -> None:
    """Test URL scrape uses IG_COOKIE_HEADER when CLI arg is omitted."""
    result = runner.invoke(
        app,
        ["scrape", "url", "--url", "https://www.instagram.com/p/ABC123/"],
        env={"IG_COOKIE_HEADER": "sessionid=env-cookie"},
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "post_url": "https://www.instagram.com/p/ABC123/",
        "output_dir": None,
        "cookie_header": "sessionid=env-cookie",
        "has_auth": True,
    }
    mock_pipeline.assert_called_once_with("url", **expected)


def test_scrape_url_missing_url() -> None:
    """Test URL scrape without required URL."""
    result = runner.invoke(app, ["scrape", "url"])

    assert result.exit_code != 0


# Test scrape_urls command


def test_scrape_urls_success(mock_pipeline: MagicMock, tmp_path: Path) -> None:
    """Test successful URLs scrape command."""
    input_file = tmp_path / "urls.json"
    input_file.write_text('{"urls": []}')

    result = runner.invoke(
        app,
        ["scrape", "urls", "--input", str(input_file)],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "input_path": input_file,
        "output_dir": None,
        "resume": False,
        "reset_output": False,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("urls", **expected)


def test_scrape_urls_with_resume_and_reset(
    mock_pipeline: MagicMock, tmp_path: Path,
) -> None:
    """Test URLs scrape with resume and reset flags."""
    input_file = tmp_path / "urls.json"
    input_file.write_text('{"urls": []}')

    result = runner.invoke(
        app,
        ["scrape", "urls", "--input", str(input_file), "--resume", "--reset-output"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "input_path": input_file,
        "output_dir": None,
        "resume": True,
        "reset_output": True,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("urls", **expected)


def test_scrape_urls_missing_input() -> None:
    """Test URLs scrape without required input."""
    result = runner.invoke(app, ["scrape", "urls"])

    assert result.exit_code != 0


# Test scrape_hashtag command


def test_scrape_hashtag_success(mock_pipeline: MagicMock) -> None:
    """Test successful hashtag scrape command."""
    result = runner.invoke(app, ["scrape", "hashtag", "--hashtag", "cats"])

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "hashtag": "cats",
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("hashtag", **expected)


def test_scrape_hashtag_with_limit(mock_pipeline: MagicMock) -> None:
    """Test hashtag scrape with limit."""
    result = runner.invoke(
        app,
        ["scrape", "hashtag", "--hashtag", "cats", "--limit", "100"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "hashtag": "cats",
        "limit": 100,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("hashtag", **expected)


def test_scrape_hashtag_missing_hashtag() -> None:
    """Test hashtag scrape without required hashtag."""
    result = runner.invoke(app, ["scrape", "hashtag"])

    assert result.exit_code != 0


# Test scrape_location command


def test_scrape_location_success(mock_pipeline: MagicMock) -> None:
    """Test successful location scrape command."""
    result = runner.invoke(app, ["scrape", "location", "--location", "nyc"])

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "location": "nyc",
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("location", **expected)


def test_scrape_location_missing_location() -> None:
    """Test location scrape without required location."""
    result = runner.invoke(app, ["scrape", "location"])

    assert result.exit_code != 0


# Test scrape_followers command


def test_scrape_followers_success(mock_pipeline: MagicMock) -> None:
    """Test successful followers scrape command."""
    result = runner.invoke(
        app,
        ["scrape", "followers", "--username", "testuser"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("followers", **expected)


def test_scrape_followers_with_limit(mock_pipeline: MagicMock) -> None:
    """Test followers scrape with limit."""
    result = runner.invoke(
        app,
        ["scrape", "followers", "--username", "testuser", "--limit", "500"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "limit": 500,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("followers", **expected)


def test_scrape_followers_missing_username() -> None:
    """Test followers scrape without required username."""
    result = runner.invoke(app, ["scrape", "followers"])

    assert result.exit_code != 0


# Test scrape_following command


def test_scrape_following_success(mock_pipeline: MagicMock) -> None:
    """Test successful following scrape command."""
    result = runner.invoke(
        app,
        ["scrape", "following", "--username", "testuser"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("following", **expected)


def test_scrape_following_missing_username() -> None:
    """Test following scrape without required username."""
    result = runner.invoke(app, ["scrape", "following"])

    assert result.exit_code != 0


# Test scrape_likers command


def test_scrape_likers_success(mock_pipeline: MagicMock) -> None:
    """Test successful likers scrape command."""
    result = runner.invoke(
        app,
        ["scrape", "likers", "--username", "testuser"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "posts_limit": None,
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("likers", **expected)


def test_scrape_likers_with_posts_limit(mock_pipeline: MagicMock) -> None:
    """Test likers scrape with posts_limit."""
    result = runner.invoke(
        app,
        [
            "scrape",
            "likers",
            "--username",
            "testuser",
            "--posts-limit",
            "10",
            "--limit",
            "100",
        ],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "posts_limit": 10,
        "limit": 100,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("likers", **expected)


def test_scrape_likers_missing_username() -> None:
    """Test likers scrape without required username."""
    result = runner.invoke(app, ["scrape", "likers"])

    assert result.exit_code != 0


# Test scrape_commenters command


def test_scrape_commenters_success(mock_pipeline: MagicMock) -> None:
    """Test successful commenters scrape command."""
    result = runner.invoke(
        app,
        ["scrape", "commenters", "--username", "testuser"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "posts_limit": None,
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("commenters", **expected)


def test_scrape_commenters_with_posts_limit(mock_pipeline: MagicMock) -> None:
    """Test commenters scrape with posts_limit."""
    result = runner.invoke(
        app,
        [
            "scrape",
            "commenters",
            "--username",
            "testuser",
            "--posts-limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "posts_limit": 5,
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("commenters", **expected)


def test_scrape_commenters_missing_username() -> None:
    """Test commenters scrape without required username."""
    result = runner.invoke(app, ["scrape", "commenters"])

    assert result.exit_code != 0


# Test scrape_stories command


def test_scrape_stories_with_username(mock_pipeline: MagicMock) -> None:
    """Test successful stories scrape with username."""
    result = runner.invoke(
        app,
        ["scrape", "stories", "--username", "testuser"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": "testuser",
        "hashtag": None,
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("stories", **expected)


def test_scrape_stories_with_hashtag(mock_pipeline: MagicMock) -> None:
    """Test successful stories scrape with hashtag."""
    result = runner.invoke(
        app,
        ["scrape", "stories", "--hashtag", "cats"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        "username": None,
        "hashtag": "cats",
        "limit": None,
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("stories", **expected)


def test_scrape_stories_neither_username_nor_hashtag() -> None:
    """Test stories scrape without username or hashtag."""
    result = runner.invoke(app, ["scrape", "stories"])

    assert result.exit_code != 0
    assert STORIES_SEED_MESSAGE in result.output


def test_scrape_stories_both_username_and_hashtag() -> None:
    """Test stories scrape with both username and hashtag."""
    result = runner.invoke(
        app,
        ["scrape", "stories", "--username", "testuser", "--hashtag", "cats"],
    )

    assert result.exit_code != 0
    assert STORIES_SEED_MESSAGE in result.output


# Test configure_scrape callback


def test_configure_scrape_default_values(mock_context: MagicMock) -> None:
    """Test configure_scrape with default values."""
    configure_scrape(
        mock_context,
        raw_captures=None,
        request_timeout=30,
        max_retries=5,
        checkpoint_every=20,
    )

    assert mock_context.obj == DEFAULT_SHARED_OPTIONS


def test_configure_scrape_with_raw_captures(mock_context: MagicMock) -> None:
    """Test configure_scrape with raw_captures enabled."""
    configure_scrape(
        mock_context,
        raw_captures=True,
        request_timeout=60,
        max_retries=10,
        checkpoint_every=50,
    )

    assert mock_context.obj == {
        "raw_captures": True,
        "request_timeout": 60,
        "max_retries": 10,
        "checkpoint_every": 50,
    }


# Test pipeline failure handling


def test_scrape_profile_pipeline_failure(mock_pipeline: MagicMock) -> None:
    """Test handling of pipeline failure."""
    mock_pipeline.return_value = 1

    result = runner.invoke(app, ["scrape", "profile", "--username", "testuser"])

    assert result.exit_code == 1


def test_scrape_profile_pipeline_exception(mock_pipeline: MagicMock) -> None:
    """Test handling of pipeline exception."""
    mock_pipeline.side_effect = Exception("Pipeline error")

    result = runner.invoke(app, ["scrape", "profile", "--username", "testuser"])

    assert result.exit_code != 0


# Test shared options propagation


def test_shared_options_propagation(mock_pipeline: MagicMock) -> None:
    """Test that shared options are propagated to pipeline."""
    result = runner.invoke(
        app,
        [
            "scrape",
            "--raw-captures",
            "--request-timeout",
            "60",
            "--max-retries",
            "10",
            "--checkpoint-every",
            "100",
            "profile",
            "--username",
            "testuser",
        ],
    )

    assert result.exit_code == 0
    call_args = mock_pipeline.call_args
    assert call_args[0][0] == "profile"
    assert call_args[1]["raw_captures"] is True
    assert call_args[1]["request_timeout"] == 60
    assert call_args[1]["max_retries"] == 10
    assert call_args[1]["checkpoint_every"] == 100


# Test output_dir as Path object


def test_output_dir_converted_to_path(mock_pipeline: MagicMock, tmp_path: Path) -> None:
    """Test that output_dir is properly converted to Path."""
    result = runner.invoke(
        app,
        ["scrape", "profile", "--username", "testuser", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    call_args = mock_pipeline.call_args
    assert isinstance(call_args[1]["output_dir"], Path)
    assert call_args[1]["output_dir"] == tmp_path


# Test all scrape commands have help


@pytest.mark.parametrize(
    "command",
    [
        ["scrape", "profile", "--help"],
        ["scrape", "url", "--help"],
        ["scrape", "urls", "--help"],
        ["scrape", "hashtag", "--help"],
        ["scrape", "location", "--help"],
        ["scrape", "followers", "--help"],
        ["scrape", "following", "--help"],
        ["scrape", "likers", "--help"],
        ["scrape", "commenters", "--help"],
        ["scrape", "stories", "--help"],
    ],
)
def test_all_commands_have_help(command: list[str]) -> None:
    """Test that all scrape commands have help text."""
    result = runner.invoke(app, command)

    assert result.exit_code == 0
    assert "Usage:" in result.output or "usage:" in result.output
