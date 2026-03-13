# Copyright (c) 2026
"""Tests for download_instagram_videos module."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instagram_scraper.workflows.video_downloads import (
    DEFAULT_USERNAME_FALLBACK,
    MEDIA_TYPE_VIDEO,
    Config,
    _default_data_dir,
    _default_output_dir,
    _default_username,
    _fetch_media_info,
    _write_post_metadata,
    _write_post_payload,
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


# Test _fetch_media_info


def test_fetch_media_info_success(
    mock_session: MagicMock,
    sample_config: Config,
) -> None:
    """Test fetching media info successfully."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [{"media_type": MEDIA_TYPE_VIDEO, "id": "12345"}],
    }

    with patch(
        "instagram_scraper.workflows._video_download_media._request_with_retry",
    ) as mock_request:
        mock_request.return_value = (mock_response, None)

        media_info, error = _fetch_media_info(mock_session, "12345", sample_config)

        assert media_info is not None
        assert error is None
        assert media_info["media_type"] == MEDIA_TYPE_VIDEO


def test_fetch_media_info_request_failure(
    mock_session: MagicMock,
    sample_config: Config,
) -> None:
    """Test fetching media info with request failure."""
    with patch(
        "instagram_scraper.workflows._video_download_media._request_with_retry",
    ) as mock_request:
        mock_request.return_value = (None, "network_error")

        media_info, error = _fetch_media_info(mock_session, "12345", sample_config)

        assert media_info is None
        assert error == "network_error"


def test_fetch_media_info_empty_items(
    mock_session: MagicMock,
    sample_config: Config,
) -> None:
    """Test fetching media info with empty items."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"items": []}

    with patch(
        "instagram_scraper.workflows._video_download_media._request_with_retry",
    ) as mock_request:
        mock_request.return_value = (mock_response, None)

        media_info, error = _fetch_media_info(mock_session, "12345", sample_config)

        assert media_info is None
        assert error == "media_info_empty"


def test_fetch_media_info_invalid_json(
    mock_session: MagicMock,
    sample_config: Config,
) -> None:
    """Test fetching media info with invalid JSON."""
    mock_response = MagicMock()
    mock_response.json.side_effect = ValueError("Invalid JSON")

    with patch(
        "instagram_scraper.workflows._video_download_media._request_with_retry",
    ) as mock_request:
        mock_request.return_value = (mock_response, None)

        with patch(
            "instagram_scraper.workflows._video_download_media._json_error",
        ) as mock_json_error:
            mock_json_error.return_value = "json_parse_error"

            media_info, error = _fetch_media_info(mock_session, "12345", sample_config)

            assert media_info is None
            assert "json_parse_error" in error


# Test _default functions


def test_default_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default data directory."""
    monkeypatch.delenv("INSTAGRAM_DATA_DIR", raising=False)
    result = _default_data_dir()
    assert result == Path("data")


def test_default_data_dir_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test data directory with env var."""
    monkeypatch.setenv("INSTAGRAM_DATA_DIR", "/custom/data")
    result = _default_data_dir()
    assert result == Path("/custom/data")


def test_default_username(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default username."""
    monkeypatch.delenv("INSTAGRAM_USERNAME", raising=False)
    result = _default_username()
    assert result == DEFAULT_USERNAME_FALLBACK


def test_default_username_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test username with env var."""
    monkeypatch.setenv("INSTAGRAM_USERNAME", "myuser")
    result = _default_username()
    assert result == "myuser"


def test_default_output_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default output directory."""
    monkeypatch.setenv("INSTAGRAM_DATA_DIR", "/data")
    monkeypatch.setenv("INSTAGRAM_USERNAME", "testuser")
    result = _default_output_dir()
    assert result == Path("/data/testuser")


# Test _write_post_payload and _write_post_metadata


def test_write_post_payload(tmp_path: Path) -> None:
    """Test writing post payload."""
    from instagram_scraper.workflows.video_downloads import _DownloadContext

    context = _DownloadContext(
        cfg=MagicMock(),
        session=MagicMock(),
        paths={"videos_root": tmp_path},
        comments_by_shortcode={},
        metrics=MagicMock(),
        completed=set(),
    )

    post_dir = _write_post_payload(
        context.paths,
        "ABC123",
        "Test caption",
        [{"text": "Test comment"}],
    )

    assert post_dir.exists()
    assert (post_dir / "caption.txt").exists()
    assert (post_dir / "comments.csv").exists()
    assert (post_dir / "caption.txt").read_text() == "Test caption"


def test_write_post_metadata(tmp_path: Path) -> None:
    """Test writing post metadata."""
    metadata = {
        "shortcode": "ABC123",
        "caption": "Test",
        "video_files": [{"position": 1}],
    }

    _write_post_metadata(tmp_path, metadata)

    metadata_path = tmp_path / "metadata.json"
    assert metadata_path.exists()
    saved = json.loads(metadata_path.read_text())
    assert saved["shortcode"] == "ABC123"


# Test _build_summary


def test_build_summary(tmp_path: Path) -> None:
    """Test building summary."""
    from instagram_scraper.workflows.video_downloads import _build_summary

    paths = {
        "videos_root": tmp_path / "videos",
        "index_csv": tmp_path / "videos_index.csv",
        "errors_csv": tmp_path / "videos_errors.csv",
    }
    metrics = {
        "processed": 10,
        "downloaded_files": 8,
        "errors": 2,
        "skipped_no_video": 0,
        "completed_shortcodes": ["ABC123"],
    }

    summary = _build_summary(tmp_path, paths, metrics, 15)

    assert summary["target_posts_considered"] == 15
    assert summary["processed"] == 10
    assert summary["downloaded_files"] == 8
    assert summary["errors"] == 2
    assert str(tmp_path / "videos_checkpoint.json") in summary["checkpoint"]
