# Copyright (c) 2026
"""Tests for download_instagram_videos module."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instagram_scraper.workflows.video_downloads import (
    MEDIA_TYPE_VIDEO,
    Config,
    _checkpoint_state,
    _increment_metric,
    _index_row,
    _mark_completed,
    _maybe_checkpoint,
    _post_metadata,
    _post_target_from_row,
    _video_entry,
    _write_comments_snapshot,
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


# Test _video_entry


def test_video_entry() -> None:
    """Test creating video entry dictionary."""
    entry = _video_entry(1, "https://example.com/video.mp4")

    assert entry["position"] == 1
    assert entry["media_type"] == MEDIA_TYPE_VIDEO
    assert entry["video_url"] == "https://example.com/video.mp4"


# Test _mark_completed


def test_mark_completed() -> None:
    """Test marking shortcode as completed."""
    metrics = {
        "processed": 0,
        "downloaded_files": 0,
        "errors": 0,
        "skipped_no_video": 0,
        "completed_shortcodes": [],
    }
    completed = set()

    _mark_completed(metrics, completed, "ABC123")

    assert "ABC123" in completed
    assert "ABC123" in metrics["completed_shortcodes"]
    assert metrics["processed"] == 1


def test_mark_completed_multiple() -> None:
    """Test marking multiple shortcodes."""
    metrics = {
        "processed": 0,
        "downloaded_files": 0,
        "errors": 0,
        "skipped_no_video": 0,
        "completed_shortcodes": [],
    }
    completed = set()

    _mark_completed(metrics, completed, "ABC123")
    _mark_completed(metrics, completed, "DEF456")
    _mark_completed(metrics, completed, "ABC123")  # Duplicate

    assert len(completed) == 2
    assert sorted(metrics["completed_shortcodes"]) == ["ABC123", "DEF456"]
    assert metrics["processed"] == 3


# Test _increment_metric


def test_increment_metric() -> None:
    """Test incrementing metrics."""
    metrics = {
        "processed": 0,
        "downloaded_files": 0,
        "errors": 0,
        "skipped_no_video": 0,
        "completed_shortcodes": [],
    }

    _increment_metric(metrics, "processed")
    _increment_metric(metrics, "downloaded_files")
    _increment_metric(metrics, "downloaded_files")
    _increment_metric(metrics, "errors")

    assert metrics["processed"] == 1
    assert metrics["downloaded_files"] == 2
    assert metrics["errors"] == 1
    assert metrics["skipped_no_video"] == 0


# Test _checkpoint_state


def test_checkpoint_state() -> None:
    """Test creating checkpoint state."""
    metrics = {
        "processed": 10,
        "downloaded_files": 8,
        "errors": 2,
        "skipped_no_video": 0,
        "completed_shortcodes": ["ABC123", "DEF456"],
    }
    completed = {"ABC123", "DEF456"}

    state = _checkpoint_state(metrics, completed)

    assert state["processed"] == 10
    assert state["downloaded_files"] == 8
    assert state["errors"] == 2
    assert state["completed_shortcodes"] == ["ABC123", "DEF456"]


# Test _maybe_checkpoint


def test_maybe_checkpoint_triggers(tmp_path: Path) -> None:
    """Test checkpoint triggers at interval."""
    from instagram_scraper.workflows.video_downloads import _DownloadContext

    config = Config(
        output_dir=tmp_path,
        posts_csv=tmp_path / "posts.csv",
        comments_csv=tmp_path / "comments.csv",
        should_resume=False,
        should_reset_output=False,
        min_delay=0.01,
        max_delay=0.02,
        max_retries=3,
        timeout=30,
        checkpoint_every=5,
        limit=None,
        cookie_header="",
        max_concurrent_downloads=2,
    )
    context = _DownloadContext(
        cfg=config,
        session=MagicMock(),
        paths={
            "videos_root": config.output_dir / "videos",
            "index_csv": config.output_dir / "videos_index.csv",
            "errors_csv": config.output_dir / "videos_errors.csv",
            "index_header": [],
            "error_header": [],
        },
        comments_by_shortcode={},
        metrics={
            "processed": 5,
            "downloaded_files": 3,
            "errors": 0,
            "skipped_no_video": 0,
            "completed_shortcodes": [],
        },
        completed=set(),
    )

    with patch(
        "instagram_scraper.workflows.video_downloads._save_checkpoint",
    ) as mock_save:
        _maybe_checkpoint(context)
        mock_save.assert_called_once()


def test_maybe_checkpoint_not_triggered(tmp_path: Path) -> None:
    """Test checkpoint doesn't trigger between intervals."""
    from instagram_scraper.workflows.video_downloads import _DownloadContext

    config = Config(
        output_dir=tmp_path,
        posts_csv=tmp_path / "posts.csv",
        comments_csv=tmp_path / "comments.csv",
        should_resume=False,
        should_reset_output=False,
        min_delay=0.01,
        max_delay=0.02,
        max_retries=3,
        timeout=30,
        checkpoint_every=5,
        limit=None,
        cookie_header="",
        max_concurrent_downloads=2,
    )
    context = _DownloadContext(
        cfg=config,
        session=MagicMock(),
        paths={
            "videos_root": config.output_dir / "videos",
            "index_csv": config.output_dir / "videos_index.csv",
            "errors_csv": config.output_dir / "videos_errors.csv",
            "index_header": [],
            "error_header": [],
        },
        comments_by_shortcode={},
        metrics={
            "processed": 3,
            "downloaded_files": 2,
            "errors": 0,
            "skipped_no_video": 0,
            "completed_shortcodes": [],
        },
        completed=set(),
    )

    with patch(
        "instagram_scraper.workflows.video_downloads._save_checkpoint",
    ) as mock_save:
        _maybe_checkpoint(context)
        mock_save.assert_not_called()


# Test _post_target_from_row


def test_post_target_from_row() -> None:
    """Test creating post target from CSV row."""
    row = {
        "shortcode": "ABC123",
        "media_id": "1234567890",
        "post_url": "https://www.instagram.com/p/ABC123/",
    }

    post = _post_target_from_row(row)

    assert post.shortcode == "ABC123"
    assert post.media_id == "1234567890"
    assert post.post_url == "https://www.instagram.com/p/ABC123/"


def test_post_target_from_row_missing_fields() -> None:
    """Test creating post target with missing fields."""
    row = {}

    post = _post_target_from_row(row)

    assert post.shortcode == ""
    assert post.media_id == ""
    assert post.post_url == ""


# Test _post_metadata


def test_post_metadata() -> None:
    """Test creating post metadata."""
    from instagram_scraper.workflows.video_downloads import _PostTarget

    post = _PostTarget(
        shortcode="ABC123",
        media_id="12345",
        post_url="https://instagr.am/p/ABC123",
    )

    metadata = _post_metadata(
        post,
        caption_text="Test caption",
        comment_count_reported="10",
        comments_saved=5,
        downloaded_for_post=[
            {"position": 1, "video_url": "https://example.com/video.mp4"},
        ],
    )

    assert metadata["shortcode"] == "ABC123"
    assert metadata["media_id"] == "12345"
    assert metadata["post_url"] == "https://instagr.am/p/ABC123"
    assert metadata["caption"] == "Test caption"
    assert metadata["comment_count_reported"] == "10"
    assert metadata["comments_saved"] == 5
    assert len(metadata["video_files"]) == 1


# Test _write_comments_snapshot


def test_write_comments_snapshot(tmp_path: Path) -> None:
    """Test writing comments snapshot."""
    post_dir = tmp_path / "ABC123"
    post_dir.mkdir()

    comments = [
        {
            "media_id": "12345",
            "shortcode": "ABC123",
            "post_url": "https://instagr.am/p/ABC123",
            "id": "1",
            "created_at_utc": "2024-01-15T10:00:00+00:00",
            "text": "Test comment",
            "comment_like_count": "5",
            "owner_username": "user1",
            "owner_id": "100",
        },
    ]

    _write_comments_snapshot(post_dir, comments)

    comments_path = post_dir / "comments.csv"
    assert comments_path.exists()
    content = comments_path.read_text()
    assert "Test comment" in content
    assert "user1" in content


# Test _index_row


def test_index_row() -> None:
    """Test creating index row."""
    from instagram_scraper.workflows.video_downloads import (
        _PostTarget,
        _VideoDownloadTask,
    )

    post = _PostTarget(
        shortcode="ABC123",
        media_id="12345",
        post_url="https://instagr.am/p/ABC123",
    )
    task = _VideoDownloadTask(
        position=1,
        video_url="https://example.com/video.mp4",
        destination=Path("/tmp/ABC123_01.mp4"),
    )

    with patch("pathlib.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 1024

        row = _index_row(post, task)

        assert row["shortcode"] == "ABC123"
        assert row["media_id"] == "12345"
        assert row["position"] == 1
        assert row["video_url"] == "https://example.com/video.mp4"
        assert row["file_size_bytes"] == 1024
