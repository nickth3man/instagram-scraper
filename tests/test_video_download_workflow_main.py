# Copyright (c) 2026
"""Tests for download_instagram_videos module."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instagram_scraper.exceptions import InstagramError
from instagram_scraper.workflows.video_downloads import (
    DEFAULT_DATA_DIR_FALLBACK,
    DEFAULT_USERNAME_FALLBACK,
    MEDIA_TYPE_CAROUSEL,
    MEDIA_TYPE_VIDEO,
    MIN_CHECKPOINT,
    MIN_CONCURRENT,
    MIN_DELAY_MINIMUM,
    MIN_RETRIES,
    MIN_TIMEOUT,
    Config,
    _plan_video_downloads,
    main,
    run,
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


# Test run (main workflow)


def test_run_posts_csv_not_found(sample_config: Config) -> None:
    """Test run raises InstagramError when posts.csv is missing."""
    with pytest.raises(InstagramError, match="posts CSV not found"):
        run(sample_config)


@patch("instagram_scraper.workflows.video_downloads._build_session")
@patch("instagram_scraper.workflows._video_download_process._fetch_media_info")
def test_run_success(
    mock_fetch: MagicMock,
    mock_build_session: MagicMock,
    sample_posts_csv: Path,
    mock_session: MagicMock,
    tmp_path: Path,
) -> None:
    """Test successful run."""
    config = Config(
        output_dir=tmp_path,
        posts_csv=sample_posts_csv,
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
    mock_build_session.return_value = mock_session

    mock_fetch.return_value = (
        {
            "media_type": MEDIA_TYPE_VIDEO,
            "video_versions": [
                {"width": 1920, "height": 1080, "url": "https://example.com/video.mp4"},
            ],
        },
        None,
    )

    def mock_download_side_effect(session, video_url, destination, cfg):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"mock video content")
        return True, None

    with patch(
        "instagram_scraper.workflows._video_download_download.download_video_file",
    ) as mock_download:
        mock_download.side_effect = mock_download_side_effect

        summary = run(config)

        assert summary["processed"] == 1
        assert summary["errors"] == 0
        assert (config.output_dir / "videos_summary.json").exists()


@patch("instagram_scraper.workflows.video_downloads._build_session")
def test_run_with_resume(
    mock_build_session: MagicMock,
    sample_posts_csv: Path,
    mock_session: MagicMock,
    tmp_path: Path,
) -> None:
    """Test run with resume from checkpoint."""
    config = Config(
        output_dir=tmp_path,
        posts_csv=sample_posts_csv,
        comments_csv=tmp_path / "comments.csv",
        should_resume=True,
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
    mock_build_session.return_value = mock_session

    # Create checkpoint with completed shortcode
    checkpoint = {
        "completed_shortcodes": ["ABC123"],
        "processed": 1,
        "downloaded_files": 1,
        "errors": 0,
        "skipped_no_video": 0,
    }
    (tmp_path / "videos_checkpoint.json").write_text(json.dumps(checkpoint))

    summary = run(config)

    # Should skip the already completed post
    assert summary["processed"] == 1


@patch("instagram_scraper.workflows.video_downloads._build_session")
@patch("instagram_scraper.workflows._video_download_process._fetch_media_info")
def test_run_with_resume_processes_new_posts_from_modified_input(
    mock_fetch: MagicMock,
    mock_build_session: MagicMock,
    mock_session: MagicMock,
    tmp_path: Path,
) -> None:
    """Test resume mode skips completed posts and processes newly added rows."""
    posts_csv = tmp_path / "posts.csv"
    with posts_csv.open("w", newline="", encoding="utf-8") as f:
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
                "Already completed",
                "1",
            ],
        )
        writer.writerow(
            [
                "NEW456",
                "9999999999",
                "https://www.instagram.com/p/NEW456/",
                str(MEDIA_TYPE_VIDEO),
                "New post after checkpoint",
                "2",
            ],
        )

    checkpoint = {
        "completed_shortcodes": ["ABC123"],
        "processed": 1,
        "downloaded_files": 1,
        "errors": 0,
        "skipped_no_video": 0,
    }
    (tmp_path / "videos_checkpoint.json").write_text(json.dumps(checkpoint))

    config = Config(
        output_dir=tmp_path,
        posts_csv=posts_csv,
        comments_csv=tmp_path / "comments.csv",
        should_resume=True,
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
    mock_build_session.return_value = mock_session
    mock_fetch.return_value = (
        {
            "media_type": MEDIA_TYPE_VIDEO,
            "video_versions": [
                {"width": 1920, "height": 1080, "url": "https://example.com/video.mp4"},
            ],
        },
        None,
    )

    def mock_download_side_effect(session, video_url, destination, cfg):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"mock video content")
        return True, None

    with patch(
        "instagram_scraper.workflows._video_download_download.download_video_file",
    ) as mock_download:
        mock_download.side_effect = mock_download_side_effect

        summary = run(config)

    assert summary["target_posts_considered"] == 2
    assert summary["processed"] == 2
    assert summary["downloaded_files"] == 2
    assert mock_fetch.call_count == 1
    assert mock_fetch.call_args.args[1] == "9999999999"
    assert not (tmp_path / "videos" / "ABC123").exists()
    assert (tmp_path / "videos" / "NEW456" / "NEW456_01.mp4").exists()


@patch("instagram_scraper.workflows.video_downloads._build_session")
@patch("instagram_scraper.workflows._video_download_process._fetch_media_info")
def test_run_with_resume_ignores_invalid_checkpoint(
    mock_fetch: MagicMock,
    mock_build_session: MagicMock,
    sample_posts_csv: Path,
    mock_session: MagicMock,
    tmp_path: Path,
) -> None:
    """Test resume mode falls back to a fresh run when checkpoint JSON is invalid."""
    config = Config(
        output_dir=tmp_path,
        posts_csv=sample_posts_csv,
        comments_csv=tmp_path / "comments.csv",
        should_resume=True,
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
    mock_build_session.return_value = mock_session
    mock_fetch.return_value = (
        {
            "media_type": MEDIA_TYPE_VIDEO,
            "video_versions": [
                {"width": 1920, "height": 1080, "url": "https://example.com/video.mp4"},
            ],
        },
        None,
    )
    (tmp_path / "videos_checkpoint.json").write_text("{not valid json")

    def mock_download_side_effect(session, video_url, destination, cfg):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"mock video content")
        return True, None

    with patch(
        "instagram_scraper.workflows._video_download_download.download_video_file",
    ) as mock_download:
        mock_download.side_effect = mock_download_side_effect

        summary = run(config)

    assert summary["processed"] == 1
    assert summary["downloaded_files"] == 1
    assert mock_fetch.call_count == 1
    saved_checkpoint = json.loads((tmp_path / "videos_checkpoint.json").read_text())
    assert saved_checkpoint["completed"] is True


# Test main


@patch("instagram_scraper.workflows.video_downloads.parse_args")
@patch("instagram_scraper.workflows.video_downloads.run")
def test_main_success(mock_run: MagicMock, mock_parse: MagicMock, capsys) -> None:
    """Test main function output."""
    mock_parse.return_value = Config(
        output_dir=Path("data/testuser"),
        posts_csv=Path("data/testuser/posts.csv"),
        comments_csv=Path("data/testuser/comments.csv"),
        should_resume=False,
        should_reset_output=False,
        min_delay=0.05,
        max_delay=0.2,
        max_retries=5,
        timeout=60,
        checkpoint_every=20,
        limit=None,
        cookie_header="",
        max_concurrent_downloads=3,
    )
    mock_run.return_value = {"processed": 10, "downloaded_files": 8}

    main()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["processed"] == 10
    assert output["downloaded_files"] == 8


# Test constants


def test_default_constants() -> None:
    """Test default constant values."""
    assert DEFAULT_DATA_DIR_FALLBACK == "data"
    assert DEFAULT_USERNAME_FALLBACK == "target_profile"
    assert MEDIA_TYPE_VIDEO == 2
    assert MEDIA_TYPE_CAROUSEL == 8
    assert MIN_DELAY_MINIMUM == 0.0
    assert MIN_RETRIES == 1
    assert MIN_TIMEOUT == 5
    assert MIN_CHECKPOINT == 1
    assert MIN_CONCURRENT == 1


# Test _plan_video_downloads


def test_plan_video_downloads() -> None:
    """Test planning video downloads."""
    from instagram_scraper.workflows.video_downloads import _PostTarget

    post = _PostTarget(
        shortcode="ABC123",
        media_id="12345",
        post_url="https://instagr.am/p/ABC123",
    )
    post_dir = Path("/tmp/videos/ABC123")

    video_entries = [
        {"position": 1, "video_url": "https://example.com/video1.mp4"},
        {"position": 2, "video_url": "https://example.com/video2.mp4"},
    ]

    tasks = _plan_video_downloads(post, video_entries, post_dir)

    assert len(tasks) == 2
    assert tasks[0].position == 1
    assert tasks[0].destination == Path("/tmp/videos/ABC123/ABC123_01.mp4")
    assert tasks[1].position == 2
    assert tasks[1].destination == Path("/tmp/videos/ABC123/ABC123_02.mp4")
