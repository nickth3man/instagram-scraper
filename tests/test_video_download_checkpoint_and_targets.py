# Copyright (c) 2026
"""Tests for download_instagram_videos module."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from instagram_scraper.workflows.video_download_support import (
    iter_target_rows,
)
from instagram_scraper.workflows.video_downloads import (
    MEDIA_TYPE_CAROUSEL,
    MEDIA_TYPE_VIDEO,
    Config,
    _initial_metrics,
    _load_checkpoint,
    _prepare_output,
    _save_checkpoint,
    _target_rows,
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


# Test _load_checkpoint


def test_load_checkpoint_valid(tmp_path: Path) -> None:
    """Test loading valid checkpoint."""
    checkpoint_path = tmp_path / "videos_checkpoint.json"
    checkpoint_data = {
        "completed_shortcodes": ["ABC123", "DEF456"],
        "processed": 10,
        "downloaded_files": 8,
        "errors": 2,
        "skipped_no_video": 0,
        "completed": True,
    }
    checkpoint_path.write_text(json.dumps(checkpoint_data))

    result = _load_checkpoint(tmp_path)

    assert result is not None
    assert result["processed"] == 10
    assert result["downloaded_files"] == 8
    assert result["completed_shortcodes"] == ["ABC123", "DEF456"]


def test_load_checkpoint_missing(tmp_path: Path) -> None:
    """Test loading checkpoint when file doesn't exist."""
    result = _load_checkpoint(tmp_path)

    assert result is None


def test_load_checkpoint_invalid_json(tmp_path: Path) -> None:
    """Test loading corrupted checkpoint."""
    checkpoint_path = tmp_path / "videos_checkpoint.json"
    checkpoint_path.write_text("not valid json")

    result = _load_checkpoint(tmp_path)

    assert result is None


# Test _save_checkpoint


def test_save_checkpoint(tmp_path: Path) -> None:
    """Test saving checkpoint."""
    state = {
        "completed_shortcodes": ["ABC123"],
        "processed": 5,
        "downloaded_files": 5,
        "errors": 0,
        "skipped_no_video": 0,
    }

    _save_checkpoint(tmp_path, state)

    checkpoint_path = tmp_path / "videos_checkpoint.json"
    assert checkpoint_path.exists()
    saved = json.loads(checkpoint_path.read_text())
    assert saved["processed"] == 5
    assert saved["completed_shortcodes"] == ["ABC123"]


# Test _target_rows


def test_target_rows_filters_by_type(tmp_path: Path) -> None:
    """Test filtering rows by media type."""
    csv_path = tmp_path / "posts.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shortcode", "media_id", "post_url", "type", "caption"])
        writer.writerow(["IMG001", "1", "https://instagr.am/p/IMG001", "1", "Image"])
        writer.writerow(
            [
                "VID001",
                "2",
                "https://instagr.am/p/VID001",
                str(MEDIA_TYPE_VIDEO),
                "Video",
            ],
        )
        writer.writerow(
            [
                "CAR001",
                "3",
                "https://instagr.am/p/CAR001",
                str(MEDIA_TYPE_CAROUSEL),
                "Carousel",
            ],
        )

    rows = _target_rows(csv_path, limit=None)

    assert len(rows) == 2
    assert rows[0]["shortcode"] == "VID001"  # Videos first
    assert rows[1]["shortcode"] == "CAR001"  # Carousels second


def test_target_rows_with_limit(tmp_path: Path) -> None:
    """Test applying limit to rows."""
    csv_path = tmp_path / "posts.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shortcode", "media_id", "post_url", "type", "caption"])
        for i in range(10):
            writer.writerow(
                [
                    f"VID{i:03d}",
                    str(i),
                    f"https://instagr.am/p/VID{i:03d}",
                    str(MEDIA_TYPE_VIDEO),
                    f"Video {i}",
                ],
            )

    rows = _target_rows(csv_path, limit=3)

    assert len(rows) == 3


def test_iter_target_rows_stops_early_with_low_limit(tmp_path: Path) -> None:
    """Test streaming target iteration stops without reading full result sets."""
    csv_path = tmp_path / "posts.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shortcode", "media_id", "post_url", "type", "caption"])
        writer.writerow(
            [
                "VID001",
                "1",
                "https://instagr.am/p/VID001",
                str(MEDIA_TYPE_VIDEO),
                "Video 1",
            ],
        )
        writer.writerow(
            [
                "VID002",
                "2",
                "https://instagr.am/p/VID002",
                str(MEDIA_TYPE_VIDEO),
                "Video 2",
            ],
        )
        writer.writerow(
            [
                "CAR001",
                "3",
                "https://instagr.am/p/CAR001",
                str(MEDIA_TYPE_CAROUSEL),
                "Carousel 1",
            ],
        )

    rows = list(iter_target_rows(csv_path, limit=2))

    assert [row["shortcode"] for row in rows] == ["VID001", "VID002"]


def test_iter_target_rows_handles_large_synthetic_fixture(tmp_path: Path) -> None:
    """Test larger synthetic inputs still yield videos first and stop at limit."""
    csv_path = tmp_path / "posts.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shortcode", "media_id", "post_url", "type", "caption"])
        for index in range(250):
            writer.writerow(
                [
                    f"IMG{index:04d}",
                    f"img-{index}",
                    f"https://instagr.am/p/IMG{index:04d}",
                    "1",
                    f"Image {index}",
                ],
            )
            writer.writerow(
                [
                    f"VID{index:04d}",
                    f"vid-{index}",
                    f"https://instagr.am/p/VID{index:04d}",
                    str(MEDIA_TYPE_VIDEO),
                    f"Video {index}",
                ],
            )
            writer.writerow(
                [
                    f"CAR{index:04d}",
                    f"car-{index}",
                    f"https://instagr.am/p/CAR{index:04d}",
                    str(MEDIA_TYPE_CAROUSEL),
                    f"Carousel {index}",
                ],
            )

    rows = list(iter_target_rows(csv_path, limit=7))

    assert [row["shortcode"] for row in rows] == [
        f"VID{index:04d}" for index in range(7)
    ]
    assert {row["type"] for row in rows} == {str(MEDIA_TYPE_VIDEO)}


def test_target_rows_empty_csv(tmp_path: Path) -> None:
    """Test handling empty CSV."""
    csv_path = tmp_path / "posts.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shortcode", "media_id", "post_url", "type", "caption"])

    rows = _target_rows(csv_path, limit=None)

    assert len(rows) == 0


# Test _initial_metrics


def test_initial_metrics_no_checkpoint() -> None:
    """Test initial metrics without checkpoint."""
    metrics = _initial_metrics(None)

    assert metrics["processed"] == 0
    assert metrics["downloaded_files"] == 0
    assert metrics["errors"] == 0
    assert metrics["skipped_no_video"] == 0
    assert metrics["completed_shortcodes"] == []


def test_initial_metrics_with_checkpoint() -> None:
    """Test initial metrics with checkpoint."""
    checkpoint = {
        "processed": 10,
        "downloaded_files": 8,
        "errors": 2,
        "skipped_no_video": 0,
        "completed_shortcodes": ["ABC123", "DEF456"],
    }

    metrics = _initial_metrics(checkpoint)

    assert metrics["processed"] == 10
    assert metrics["downloaded_files"] == 8
    assert metrics["errors"] == 2
    assert metrics["completed_shortcodes"] == ["ABC123", "DEF456"]


# Test _prepare_output


def test_prepare_output_creates_directories(sample_config: Config) -> None:
    """Test that _prepare_output creates necessary directories."""
    paths = _prepare_output(sample_config)

    assert paths["videos_root"].exists()
    assert paths["videos_root"].is_dir()
    assert paths["index_csv"].exists()
    assert paths["errors_csv"].exists()


def test_prepare_output_reset_mode(tmp_path: Path) -> None:
    """Test reset mode clears existing files."""
    # Create existing files
    videos_root = tmp_path / "videos"
    videos_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "videos_index.csv").write_text("old data")
    (tmp_path / "videos_errors.csv").write_text("old errors")
    (tmp_path / "videos_checkpoint.json").write_text('{"old": "checkpoint"}')
    (tmp_path / "videos_summary.json").write_text('{"old": "summary"}')

    # Create config with reset enabled
    config = Config(
        output_dir=tmp_path,
        posts_csv=tmp_path / "posts.csv",
        comments_csv=tmp_path / "comments.csv",
        should_resume=False,
        should_reset_output=True,
        min_delay=0.01,
        max_delay=0.02,
        max_retries=3,
        timeout=30,
        checkpoint_every=10,
        limit=None,
        cookie_header="",
        max_concurrent_downloads=2,
    )
    _prepare_output(config)

    # Files should be recreated fresh
    assert (tmp_path / "videos_index.csv").exists()
    assert (tmp_path / "videos_errors.csv").exists()
    # Checkpoint and summary should be removed
    assert not (tmp_path / "videos_checkpoint.json").exists()
    assert not (tmp_path / "videos_summary.json").exists()
