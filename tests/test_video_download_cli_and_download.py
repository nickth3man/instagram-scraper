# Copyright (c) 2026
"""Tests for download_instagram_videos module."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instagram_scraper.workflows.video_downloads import (
    MEDIA_TYPE_VIDEO,
    MIN_CHECKPOINT,
    MIN_CONCURRENT,
    MIN_DELAY_MINIMUM,
    MIN_RETRIES,
    MIN_TIMEOUT,
    Config,
    download_video_file,
    parse_args,
)

# Fixtures


@pytest.fixture
def sample_config(tmp_path: Path) -> Config:
    """Create a sample Config for testing."""
    return Config(
        output_dir=tmp_path,
        posts_csv=tmp_path / "posts.csv",
        comments_csv=tmp_path / "comments.csv",
        should_resume=False,
        should_reset_output=False,
        min_delay=0.01,
        max_delay=0.02,
        max_retries=3,
        timeout=30,
        checkpoint_every=10,
        limit=None,
        cookie_header="",
        max_concurrent_downloads=2,
    )


@pytest.fixture
def sample_posts_csv(tmp_path: Path) -> Path:
    """Create a sample posts.csv file."""
    csv_path = tmp_path / "posts.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "shortcode",
                "media_id",
                "post_url",
                "type",
                "caption",
                "comment_count",
            ],
        )
        writer.writerow(
            [
                "ABC123",
                "1234567890",
                "https://www.instagram.com/p/ABC123/",
                str(MEDIA_TYPE_VIDEO),
                "Test caption",
                "5",
            ],
        )
    return csv_path


@pytest.fixture
def sample_comments_csv(tmp_path: Path) -> Path:
    """Create a sample comments.csv file."""
    csv_path = tmp_path / "comments.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "media_id",
                "shortcode",
                "post_url",
                "id",
                "created_at_utc",
                "text",
                "comment_like_count",
                "owner_username",
                "owner_id",
            ],
        )
        writer.writerow(
            [
                "1234567890",
                "ABC123",
                "https://www.instagram.com/p/ABC123/",
                "1",
                "2024-01-15T10:00:00+00:00",
                "Test comment",
                "10",
                "commenter1",
                "100",
            ],
        )
    return csv_path


@pytest.fixture
def mock_response() -> MagicMock:
    """Create a mock requests Response."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "video/mp4"}
    response.iter_content.return_value = [b"video", b"content", b"chunks"]
    response.close = MagicMock()
    return response


@pytest.fixture
def mock_session(mock_response: MagicMock) -> MagicMock:
    """Create a mock requests Session."""
    session = MagicMock()
    session.get.return_value = mock_response
    session.close = MagicMock()
    return session


# Test parse_args


@patch("instagram_scraper.workflows._video_download_cli.argparse.ArgumentParser")
def test_parse_args_defaults(mock_parser_class: MagicMock) -> None:
    """Test parse_args with default values."""
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser

    args = MagicMock()
    args.output_dir = "data/testuser"
    args.posts_csv = "data/testuser/posts.csv"
    args.comments_csv = "data/testuser/comments.csv"
    args.resume = False
    args.reset_output = False
    args.min_delay = 0.05
    args.max_delay = 0.2
    args.max_retries = 5
    args.timeout = 60
    args.checkpoint_every = 20
    args.limit = None
    args.cookie_header = ""
    args.max_concurrent_downloads = 3
    mock_parser.parse_args.return_value = args

    config = parse_args()

    assert isinstance(config, Config)
    assert config.min_delay == 0.05
    assert config.max_delay == 0.2
    assert config.max_retries == 5
    assert config.timeout == 60


@patch.dict(os.environ, {"IG_COOKIE_HEADER": "sessionid=abc123"})
@patch("instagram_scraper.workflows._video_download_cli.argparse.ArgumentParser")
def test_parse_args_cookie_from_env(mock_parser_class: MagicMock) -> None:
    """Test parse_args reads cookie from environment."""
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser

    args = MagicMock()
    args.output_dir = "data/testuser"
    args.posts_csv = "data/testuser/posts.csv"
    args.comments_csv = "data/testuser/comments.csv"
    args.resume = False
    args.reset_output = False
    args.min_delay = 0.05
    args.max_delay = 0.2
    args.max_retries = 5
    args.timeout = 60
    args.checkpoint_every = 20
    args.limit = None
    args.cookie_header = "sessionid=abc123"
    args.max_concurrent_downloads = 3
    mock_parser.parse_args.return_value = args

    config = parse_args()

    assert config.cookie_header == "sessionid=abc123"


@patch("instagram_scraper.workflows._video_download_cli.argparse.ArgumentParser")
def test_parse_args_validation(mock_parser_class: MagicMock) -> None:
    """Test parse_args validates minimum values."""
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser

    args = MagicMock()
    args.output_dir = "data/testuser"
    args.posts_csv = "data/testuser/posts.csv"
    args.comments_csv = "data/testuser/comments.csv"
    args.resume = False
    args.reset_output = False
    args.min_delay = -1.0
    args.max_delay = -2.0
    args.max_retries = 0
    args.timeout = 1
    args.checkpoint_every = 0
    args.limit = None
    args.cookie_header = ""
    args.max_concurrent_downloads = 0
    mock_parser.parse_args.return_value = args

    config = parse_args()

    assert config.min_delay == MIN_DELAY_MINIMUM
    assert config.max_delay >= args.min_delay  # max_delay should be at least min_delay
    assert config.max_retries == MIN_RETRIES
    assert config.timeout == MIN_TIMEOUT
    assert config.checkpoint_every == MIN_CHECKPOINT
    assert config.max_concurrent_downloads == MIN_CONCURRENT


# Test download_video_file


def test_download_video_file_success(
    mock_session: MagicMock,
    mock_response: MagicMock,
    sample_config: Config,
    tmp_path: Path,
) -> None:
    """Test successful video download."""
    destination = tmp_path / "test_video.mp4"

    success, error = download_video_file(
        mock_session,
        "https://example.com/video.mp4",
        destination,
        sample_config,
    )

    assert success is True
    assert error is None
    assert destination.exists()
    assert destination.read_bytes() == b"video" + b"content" + b"chunks"


def test_download_video_file_skip_existing(
    mock_session: MagicMock,
    sample_config: Config,
    tmp_path: Path,
) -> None:
    """Test skipping download for existing file."""
    destination = tmp_path / "test_video.mp4"
    destination.write_bytes(b"existing content")

    success, error = download_video_file(
        mock_session,
        "https://example.com/video.mp4",
        destination,
        sample_config,
    )

    assert success is True
    assert error is None
    mock_session.get.assert_not_called()


def test_download_video_file_empty_existing(
    mock_session: MagicMock,
    mock_response: MagicMock,
    sample_config: Config,
    tmp_path: Path,
) -> None:
    """Test re-download when existing file is empty."""
    destination = tmp_path / "test_video.mp4"
    destination.write_bytes(b"")

    success, error = download_video_file(
        mock_session,
        "https://example.com/video.mp4",
        destination,
        sample_config,
    )

    assert success is True
    assert error is None
    mock_session.get.assert_called_once()


def test_download_video_file_request_failure(
    mock_session: MagicMock,
    sample_config: Config,
    tmp_path: Path,
) -> None:
    """Test handling request failure."""
    with patch(
        "instagram_scraper.workflows._video_download_download._request_with_retry",
    ) as mock_request:
        mock_request.return_value = (None, "network_error")

        destination = tmp_path / "test_video.mp4"
        success, error = download_video_file(
            mock_session,
            "https://example.com/video.mp4",
            destination,
            sample_config,
        )

        assert success is False
        assert error == "network_error"


def test_download_video_file_empty_response(
    mock_session: MagicMock,
    sample_config: Config,
    tmp_path: Path,
) -> None:
    """Test handling empty response content."""
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b""]
    mock_response.close = MagicMock()

    with patch(
        "instagram_scraper.workflows._video_download_download._request_with_retry",
    ) as mock_request:
        mock_request.return_value = (mock_response, None)

        destination = tmp_path / "test_video.mp4"
        success, error = download_video_file(
            mock_session,
            "https://example.com/video.mp4",
            destination,
            sample_config,
        )

        assert success is False
        assert error == "video_file_empty"


def test_download_video_file_write_error(
    mock_session: MagicMock,
    sample_config: Config,
    tmp_path: Path,
) -> None:
    """Test handling write error during download."""
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"data"]
    mock_response.close = MagicMock()

    with patch(
        "instagram_scraper.workflows._video_download_download._request_with_retry",
    ) as mock_request:
        mock_request.return_value = (mock_response, None)

        with patch("pathlib.Path.open") as mock_open:
            mock_open.side_effect = OSError("Disk full")

            destination = tmp_path / "test_video.mp4"
            success, error = download_video_file(
                mock_session,
                "https://example.com/video.mp4",
                destination,
                sample_config,
            )

            assert success is False
            assert "file_write_error" in error
