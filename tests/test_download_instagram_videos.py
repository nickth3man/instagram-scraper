# Copyright (c) 2026
"""Tests for download_instagram_videos module."""

from __future__ import annotations

import csv
import json
import os
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instagram_scraper.workflows.video_download_support import (
    CommentsLookup,
    DownloadSessionPool,
    iter_target_rows,
)
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
    _checkpoint_state,
    _default_data_dir,
    _default_output_dir,
    _default_username,
    _extract_video_entries,
    _fetch_media_info,
    _increment_metric,
    _index_row,
    _initial_metrics,
    _load_checkpoint,
    _load_comments_by_shortcode,
    _mark_completed,
    _maybe_checkpoint,
    _pick_best_video_url,
    _plan_video_downloads,
    _post_metadata,
    _post_target_from_row,
    _prepare_output,
    _save_checkpoint,
    _target_rows,
    _validate_post_target,
    _video_entry,
    _write_comments_snapshot,
    _write_post_metadata,
    _write_post_payload,
    download_video_file,
    main,
    parse_args,
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


# Test parse_args


@patch("instagram_scraper.workflows.video_downloads.argparse.ArgumentParser")
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
@patch("instagram_scraper.workflows.video_downloads.argparse.ArgumentParser")
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


@patch("instagram_scraper.workflows.video_downloads.argparse.ArgumentParser")
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
        "instagram_scraper.workflows.video_downloads._request_with_retry",
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
        "instagram_scraper.workflows.video_downloads._request_with_retry",
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
        "instagram_scraper.workflows.video_downloads._request_with_retry",
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
        shortcode="ABC123", media_id="12345", post_url="https://instagr.am/p/ABC123",
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
        shortcode="", media_id="12345", post_url="https://instagr.am/p/ABC123",
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
        shortcode="ABC123", media_id="", post_url="https://instagr.am/p/ABC123",
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
        shortcode="ABC123", media_id="12345", post_url="https://instagr.am/p/ABC123",
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
        shortcode="ABC123", media_id="12345", post_url="https://instagr.am/p/ABC123",
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


# Test run (main workflow)


def test_run_posts_csv_not_found(sample_config: Config) -> None:
    """Test run raises FileNotFoundError when posts.csv missing."""
    with pytest.raises(FileNotFoundError):
        run(sample_config)


@patch("instagram_scraper.workflows.video_downloads._build_session")
@patch("instagram_scraper.workflows.video_downloads._fetch_media_info")
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
        "instagram_scraper.workflows.video_downloads.download_video_file",
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
@patch("instagram_scraper.workflows.video_downloads._fetch_media_info")
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
        "instagram_scraper.workflows.video_downloads.download_video_file",
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
@patch("instagram_scraper.workflows.video_downloads._fetch_media_info")
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
        "instagram_scraper.workflows.video_downloads.download_video_file",
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
        shortcode="ABC123", media_id="12345", post_url="https://instagr.am/p/ABC123",
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
        "instagram_scraper.workflows.video_downloads._request_with_retry",
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
        "instagram_scraper.workflows.video_downloads._request_with_retry",
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
        "instagram_scraper.workflows.video_downloads._request_with_retry",
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
        "instagram_scraper.workflows.video_downloads._request_with_retry",
    ) as mock_request:
        mock_request.return_value = (mock_response, None)

        with patch(
            "instagram_scraper.workflows.video_downloads._json_error",
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
        context,
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
