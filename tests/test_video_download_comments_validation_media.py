# Copyright (c) 2026
"""Tests for download_instagram_videos module."""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instagram_scraper.workflows.video_download_support import (
    CommentsLookup,
    DownloadSessionPool,
)
from instagram_scraper.workflows.video_downloads import (
    MEDIA_TYPE_CAROUSEL,
    MEDIA_TYPE_VIDEO,
    Config,
    _extract_video_entries,
    _load_comments_by_shortcode,
    _pick_best_video_url,
    _validate_post_target,
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


# Test _load_comments_by_shortcode


def test_load_comments_by_shortcode(sample_comments_csv: Path) -> None:
    """Test loading comments grouped by shortcode."""
    by_shortcode = _load_comments_by_shortcode(sample_comments_csv)

    assert "ABC123" in by_shortcode
    assert len(by_shortcode["ABC123"]) == 1
    assert by_shortcode["ABC123"][0]["text"] == "Test comment"


def test_load_comments_by_shortcode_missing_file(tmp_path: Path) -> None:
    """Test loading comments when file doesn't exist."""
    by_shortcode = _load_comments_by_shortcode(tmp_path / "missing.csv")

    assert by_shortcode == {}


def test_load_comments_multiple_shortcodes(tmp_path: Path) -> None:
    """Test loading comments with multiple shortcodes."""
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
                "1",
                "POST1",
                "url1",
                "1",
                "2024-01-15T10:00:00+00:00",
                "Comment 1",
                "5",
                "user1",
                "100",
            ],
        )
        writer.writerow(
            [
                "2",
                "POST1",
                "url2",
                "2",
                "2024-01-15T10:05:00+00:00",
                "Comment 2",
                "3",
                "user2",
                "101",
            ],
        )
        writer.writerow(
            [
                "3",
                "POST2",
                "url3",
                "3",
                "2024-01-15T11:00:00+00:00",
                "Comment 3",
                "10",
                "user3",
                "102",
            ],
        )

    by_shortcode = _load_comments_by_shortcode(csv_path)

    assert len(by_shortcode["POST1"]) == 2
    assert len(by_shortcode["POST2"]) == 1


def test_comments_lookup_builds_disk_backed_index(
    sample_comments_csv: Path,
    tmp_path: Path,
) -> None:
    """Test disk-backed comment lookup for larger download runs."""
    index_path = tmp_path / ".comments.sqlite3"
    lookup = CommentsLookup(sample_comments_csv, index_path)

    try:
        rows = lookup.get("ABC123")
        assert len(rows) == 1
        assert rows[0]["text"] == "Test comment"
        assert index_path.exists()
    finally:
        lookup.close()

    assert not index_path.exists()


def test_comments_lookup_handles_large_synthetic_fixture(tmp_path: Path) -> None:
    """Test disk-backed lookup returns expected rows for larger fixtures."""
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
        for shortcode_index in range(40):
            shortcode = f"POST{shortcode_index:03d}"
            for comment_index in range(25):
                writer.writerow(
                    [
                        f"media-{shortcode_index}",
                        shortcode,
                        f"https://www.instagram.com/p/{shortcode}/",
                        f"{shortcode_index}-{comment_index}",
                        "2024-01-15T10:00:00+00:00",
                        f"Comment {shortcode_index:03d}-{comment_index:02d}",
                        str(comment_index),
                        f"user{comment_index:02d}",
                        f"owner-{comment_index:02d}",
                    ],
                )

    index_path = tmp_path / ".comments.sqlite3"
    lookup = CommentsLookup(csv_path, index_path)
    try:
        rows = lookup.get("POST007")
        assert len(rows) == 25
        assert rows[0]["text"] == "Comment 007-00"
        assert rows[-1]["text"] == "Comment 007-24"
    finally:
        lookup.close()

    assert not index_path.exists()


def test_download_session_pool_is_thread_local() -> None:
    """Test downloader sessions are isolated per worker thread."""
    first_session = MagicMock()
    second_session = MagicMock()

    with patch(
        "instagram_scraper.workflows.video_download_support.build_instagram_session",
        side_effect=[first_session, second_session],
    ):
        pool = DownloadSessionPool("sessionid=abc")
        sessions: list[object] = []

        def worker() -> None:
            sessions.append(pool.get())

        main_thread_session = pool.get()
        worker_thread = threading.Thread(target=worker)
        worker_thread.start()
        worker_thread.join()

        assert main_thread_session is first_session
        assert sessions == [second_session]

        pool.close()

    first_session.close.assert_called_once()
    second_session.close.assert_called_once()


# Test _validate_post_target


def test_validate_post_target_valid() -> None:
    """Test validating valid post target."""
    from instagram_scraper.workflows.video_downloads import _PostTarget

    context = MagicMock()
    context.metrics = {"processed": 0, "errors": 0}
    post = _PostTarget(
        shortcode="ABC123",
        media_id="12345",
        post_url="https://instagr.am/p/ABC123",
    )

    is_valid = _validate_post_target(context, post)

    assert is_valid is True


def test_validate_post_target_missing_shortcode(tmp_path: Path) -> None:
    """Test validating post with missing shortcode."""
    from instagram_scraper.workflows.video_downloads import _PostTarget

    context = MagicMock()
    context.metrics = {"processed": 0, "errors": 0}
    context.paths = {
        "errors_csv": tmp_path / "errors.csv",
        "error_header": ["shortcode", "media_id", "post_url", "stage", "error"],
    }
    post = _PostTarget(
        shortcode="",
        media_id="12345",
        post_url="https://instagr.am/p/ABC123",
    )

    is_valid = _validate_post_target(context, post)

    assert is_valid is False


def test_validate_post_target_missing_media_id(tmp_path: Path) -> None:
    """Test validating post with missing media_id."""
    from instagram_scraper.workflows.video_downloads import _PostTarget

    context = MagicMock()
    context.metrics = {"processed": 0, "errors": 0}
    context.paths = {
        "errors_csv": tmp_path / "errors.csv",
        "error_header": ["shortcode", "media_id", "post_url", "stage", "error"],
    }
    post = _PostTarget(
        shortcode="ABC123",
        media_id="",
        post_url="https://instagr.am/p/ABC123",
    )

    is_valid = _validate_post_target(context, post)

    assert is_valid is False


# Test _pick_best_video_url


def test_pick_best_video_url() -> None:
    """Test picking best quality video URL."""
    video_versions = [
        {"width": 640, "height": 480, "url": "https://example.com/480p.mp4"},
        {"width": 1920, "height": 1080, "url": "https://example.com/1080p.mp4"},
        {"width": 1280, "height": 720, "url": "https://example.com/720p.mp4"},
    ]

    best_url = _pick_best_video_url(video_versions)

    assert best_url == "https://example.com/1080p.mp4"


def test_pick_best_video_url_invalid_data() -> None:
    """Test picking best URL with invalid data."""
    video_versions = [
        {"width": "invalid", "height": 480, "url": "https://example.com/bad.mp4"},
        {"width": 640, "height": "invalid", "url": "https://example.com/bad2.mp4"},
        {"width": 1280, "height": 720, "url": "https://example.com/good.mp4"},
    ]

    best_url = _pick_best_video_url(video_versions)

    assert best_url == "https://example.com/good.mp4"


def test_pick_best_video_url_not_list() -> None:
    """Test picking best URL when input is not a list."""
    assert _pick_best_video_url(None) is None
    assert _pick_best_video_url("not a list") is None
    assert _pick_best_video_url({}) is None


def test_pick_best_video_url_empty() -> None:
    """Test picking best URL from empty list."""
    assert _pick_best_video_url([]) is None


# Test _extract_video_entries


def test_extract_video_entries_video_post() -> None:
    """Test extracting video from video post."""
    media_info = {
        "media_type": MEDIA_TYPE_VIDEO,
        "video_versions": [
            {"width": 1920, "height": 1080, "url": "https://example.com/video.mp4"},
        ],
    }

    entries = _extract_video_entries(media_info)

    assert len(entries) == 1
    assert entries[0]["position"] == 1
    assert entries[0]["video_url"] == "https://example.com/video.mp4"


def test_extract_video_entries_carousel() -> None:
    """Test extracting videos from carousel post."""
    media_info = {
        "media_type": MEDIA_TYPE_CAROUSEL,
        "carousel_media": [
            {"media_type": 1},  # Image
            {
                "media_type": MEDIA_TYPE_VIDEO,
                "video_versions": [
                    {
                        "width": 1280,
                        "height": 720,
                        "url": "https://example.com/video1.mp4",
                    },
                ],
            },
            {
                "media_type": MEDIA_TYPE_VIDEO,
                "video_versions": [
                    {
                        "width": 1920,
                        "height": 1080,
                        "url": "https://example.com/video2.mp4",
                    },
                ],
            },
        ],
    }

    entries = _extract_video_entries(media_info)

    assert len(entries) == 2
    assert entries[0]["position"] == 2
    assert entries[1]["position"] == 3


def test_extract_video_entries_no_videos() -> None:
    """Test extracting videos when none present."""
    media_info = {
        "media_type": 1,  # Image only
        "image_versions2": {},
    }

    entries = _extract_video_entries(media_info)

    assert len(entries) == 0


def test_extract_video_entries_invalid_carousel() -> None:
    """Test extracting videos with invalid carousel structure."""
    media_info = {
        "media_type": MEDIA_TYPE_CAROUSEL,
        "carousel_media": "not a list",
    }

    entries = _extract_video_entries(media_info)

    assert len(entries) == 0
