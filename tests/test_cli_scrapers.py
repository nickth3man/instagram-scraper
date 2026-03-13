# Copyright (c) 2026
"""Tests for cli module - scraper commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from instagram_scraper.cli import STORIES_SEED_MESSAGE, app
from tests.conftest import (
    DEFAULT_BROWSER_SESSION_OPTIONS,
    DEFAULT_SHARED_OPTIONS,
    runner,
)

# Test scrape_profile command


def test_scrape_profile_success(mock_pipeline: MagicMock) -> None:
    result = runner.invoke(app, ["scrape", "profile", "--username", "testuser"])

    assert result.exit_code == 0
    expected = {**DEFAULT_SHARED_OPTIONS, "username": "testuser", "output_dir": None}
    mock_pipeline.assert_called_once_with("profile", **expected)


def test_scrape_profile_with_output_dir(
    mock_pipeline: MagicMock,
    tmp_path: Path,
) -> None:
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
    result = runner.invoke(app, ["scrape", "profile"])

    assert result.exit_code != 0
    assert "--username" in result.output or "Required" in result.output


# Test scrape_url command


def test_scrape_url_success(mock_pipeline: MagicMock) -> None:
    result = runner.invoke(
        app,
        ["scrape", "url", "--url", "https://www.instagram.com/p/ABC123/"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        **DEFAULT_BROWSER_SESSION_OPTIONS,
        "post_url": "https://www.instagram.com/p/ABC123/",
        "output_dir": None,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("url", **expected)


def test_scrape_url_with_cookie(mock_pipeline: MagicMock) -> None:
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
        **DEFAULT_BROWSER_SESSION_OPTIONS,
        "post_url": "https://www.instagram.com/p/ABC123/",
        "output_dir": None,
        "cookie_header": "sessionid=abc123",
        "has_auth": True,
    }
    mock_pipeline.assert_called_once_with("url", **expected)


def test_scrape_url_uses_env_cookie_default(mock_pipeline: MagicMock) -> None:
    result = runner.invoke(
        app,
        ["scrape", "url", "--url", "https://www.instagram.com/p/ABC123/"],
        env={"IG_COOKIE_HEADER": "sessionid=env-cookie"},
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        **DEFAULT_BROWSER_SESSION_OPTIONS,
        "post_url": "https://www.instagram.com/p/ABC123/",
        "output_dir": None,
        "cookie_header": "sessionid=env-cookie",
        "has_auth": True,
    }
    mock_pipeline.assert_called_once_with("url", **expected)


def test_scrape_url_missing_url() -> None:
    result = runner.invoke(app, ["scrape", "url"])

    assert result.exit_code != 0


# Test scrape_urls command


def test_scrape_urls_success(mock_pipeline: MagicMock, tmp_path: Path) -> None:
    input_file = tmp_path / "urls.json"
    input_file.write_text('{"urls": []}')

    result = runner.invoke(
        app,
        ["scrape", "urls", "--input", str(input_file)],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        **DEFAULT_BROWSER_SESSION_OPTIONS,
        "input_path": input_file,
        "output_dir": None,
        "resume": False,
        "reset_output": False,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("urls", **expected)


def test_scrape_urls_with_resume_and_reset(
    mock_pipeline: MagicMock,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "urls.json"
    input_file.write_text('{"urls": []}')

    result = runner.invoke(
        app,
        ["scrape", "urls", "--input", str(input_file), "--resume", "--reset-output"],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        **DEFAULT_BROWSER_SESSION_OPTIONS,
        "input_path": input_file,
        "output_dir": None,
        "resume": True,
        "reset_output": True,
        "cookie_header": "",
        "has_auth": False,
    }
    mock_pipeline.assert_called_once_with("urls", **expected)


def test_scrape_urls_browser_html_options(
    mock_pipeline: MagicMock,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "urls.json"
    input_file.write_text('{"urls": []}')

    result = runner.invoke(
        app,
        [
            "scrape",
            "--browser-html",
            "urls",
            "--input",
            str(input_file),
        ],
    )

    assert result.exit_code == 0
    expected = {
        **DEFAULT_SHARED_OPTIONS,
        **DEFAULT_BROWSER_SESSION_OPTIONS,
        "input_path": input_file,
        "output_dir": None,
        "resume": False,
        "reset_output": False,
        "cookie_header": "",
        "has_auth": False,
        "browser_html": True,
    }
    mock_pipeline.assert_called_once_with("urls", **expected)


def test_scrape_urls_missing_input() -> None:
    result = runner.invoke(app, ["scrape", "urls"])

    assert result.exit_code != 0


# Test scrape_hashtag command


def test_scrape_hashtag_success(mock_pipeline: MagicMock) -> None:
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
    result = runner.invoke(app, ["scrape", "hashtag"])

    assert result.exit_code != 0


# Test scrape_location command


def test_scrape_location_success(mock_pipeline: MagicMock) -> None:
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
    result = runner.invoke(app, ["scrape", "location"])

    assert result.exit_code != 0


# Test scrape_followers command


def test_scrape_followers_success(mock_pipeline: MagicMock) -> None:
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
    result = runner.invoke(app, ["scrape", "followers"])

    assert result.exit_code != 0


# Test scrape_following command


def test_scrape_following_success(mock_pipeline: MagicMock) -> None:
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
    result = runner.invoke(app, ["scrape", "following"])

    assert result.exit_code != 0


# Test scrape_likers command


def test_scrape_likers_success(mock_pipeline: MagicMock) -> None:
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
    result = runner.invoke(app, ["scrape", "likers"])

    assert result.exit_code != 0


# Test scrape_commenters command


def test_scrape_commenters_success(mock_pipeline: MagicMock) -> None:
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
    result = runner.invoke(app, ["scrape", "commenters"])

    assert result.exit_code != 0


# Test scrape_stories command


def test_scrape_stories_with_username(mock_pipeline: MagicMock) -> None:
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
    result = runner.invoke(app, ["scrape", "stories"])

    assert result.exit_code != 0
    assert STORIES_SEED_MESSAGE in result.output


def test_scrape_stories_both_username_and_hashtag() -> None:
    result = runner.invoke(
        app,
        ["scrape", "stories", "--username", "testuser", "--hashtag", "cats"],
    )

    assert result.exit_code != 0
    assert STORIES_SEED_MESSAGE in result.output


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
    result = runner.invoke(app, command)

    assert result.exit_code == 0
    assert "Usage:" in result.output or "usage:" in result.output
