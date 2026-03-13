# Copyright (c) 2026
"""Tests for cli module - core functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from instagram_scraper.cli import app, configure_scrape
from tests.conftest import DEFAULT_SHARED_OPTIONS, runner

# Test CLI App Structure


def test_app_has_scrape_subcommand() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scrape" in result.output


def test_scrape_app_has_subcommands() -> None:
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


# Test configure_scrape callback


def test_configure_scrape_default_values(
    mock_context: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "instagram_scraper.cli.click.get_current_context",
        lambda: mock_context,
    )
    configure_scrape(
        raw_captures=None,
        request_timeout=30,
        max_retries=5,
        checkpoint_every=20,
    )

    assert mock_context.obj == DEFAULT_SHARED_OPTIONS


def test_configure_scrape_with_raw_captures(
    mock_context: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "instagram_scraper.cli.click.get_current_context",
        lambda: mock_context,
    )
    configure_scrape(
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
        "browser_html": False,
    }


# Test pipeline failure handling


def test_scrape_profile_pipeline_failure(mock_pipeline: MagicMock) -> None:
    mock_pipeline.return_value = 1

    result = runner.invoke(app, ["scrape", "profile", "--username", "testuser"])

    assert result.exit_code == 1


def test_scrape_profile_pipeline_exception(mock_pipeline: MagicMock) -> None:
    mock_pipeline.side_effect = Exception("Pipeline error")

    result = runner.invoke(app, ["scrape", "profile", "--username", "testuser"])

    assert result.exit_code != 0


# Test shared options propagation


def test_shared_options_propagation(mock_pipeline: MagicMock) -> None:
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
    result = runner.invoke(app, command)

    assert result.exit_code == 0
    assert "Usage:" in result.output or "usage:" in result.output
