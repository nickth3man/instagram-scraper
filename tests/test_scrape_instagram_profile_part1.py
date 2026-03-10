# Copyright (c) 2026
"""Tests for scrape_instagram_profile module."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from instaloader.exceptions import InstaloaderException

from instagram_scraper.workflows.profile import (
    _collect_comments,
    _comment_row,
    _create_dataset_dict,
    _create_instaloader,
    _create_summary_dict,
    _get_output_dir,
    _iter_post_rows,
    _parse_args,
    _write_comments_csv,
    _write_posts_csv,
    comment_to_dict,
)

# Fixtures


@pytest.fixture
def mock_post(mocker) -> MagicMock:
    """Create a mock Instagram Post object."""
    post = mocker.MagicMock()
    post.shortcode = "ABC123"
    post.date_utc = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    post.caption = "Test caption"
    post.likes = 100
    post.comments = 5
    post.is_video = True
    post.typename = "GraphVideo"
    post.get_comments.return_value = []
    return post


@pytest.fixture
def mock_comment(mocker) -> MagicMock:
    """Create a mock Instagram Comment object."""
    comment = mocker.MagicMock()
    comment.id = 12345
    comment.text = "Test comment text"
    comment.created_at_utc = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)
    comment.likes_count = 10

    owner = mocker.MagicMock()
    owner.username = "commenter_user"
    owner.userid = 67890
    comment.owner = owner

    comment.answers = []
    return comment


@pytest.fixture
def mock_reply(mocker) -> MagicMock:
    """Create a mock reply Comment object."""
    reply = mocker.MagicMock()
    reply.id = 12346
    reply.text = "Reply text"
    reply.created_at_utc = datetime(2024, 1, 15, 11, 5, 0, tzinfo=UTC)
    reply.likes_count = 3

    owner = mocker.MagicMock()
    owner.username = "replier_user"
    owner.userid = 67891
    reply.owner = owner

    return reply


@pytest.fixture
def mock_profile(mocker, mock_post) -> MagicMock:
    """Create a mock Instagram Profile object."""
    profile = mocker.MagicMock()
    profile.get_posts.return_value = [mock_post]
    return profile


@pytest.fixture
def mock_instaloader(mocker) -> MagicMock:
    """Create a mock Instaloader instance."""
    loader = mocker.MagicMock()
    loader.context = mocker.MagicMock()
    loader.context.quotamessages = None
    return loader


# Test comment_to_dict


def test_comment_to_dict_top_level(mock_comment: MagicMock) -> None:
    """Test converting a top-level comment to dict."""
    result = comment_to_dict(mock_comment)

    assert result["id"] == "12345"
    assert result["parent_id"] is None
    assert result["text"] == "Test comment text"
    assert result["created_at_utc"] == "2024-01-15T11:00:00+00:00"
    assert result["comment_like_count"] == 10
    assert result["owner_username"] == "commenter_user"
    assert result["owner_id"] == "67890"


def test_comment_to_dict_with_parent(mock_comment: MagicMock) -> None:
    """Test converting a reply comment with parent_id."""
    result = comment_to_dict(mock_comment, parent_id=99999)

    assert result["parent_id"] == "99999"


def test_comment_to_dict_missing_fields(mocker: pytest.MockFixture) -> None:
    """Test converting a comment with missing fields."""
    comment = mocker.MagicMock()
    comment.id = None
    comment.text = None
    comment.created_at_utc = None
    comment.likes_count = None
    comment.owner = None

    result = comment_to_dict(comment)

    assert result["id"] == "None"
    assert result["text"] is None
    assert result["created_at_utc"] is None
    assert result["comment_like_count"] is None
    assert result["owner_username"] is None
    assert result["owner_id"] is None


# Test _parse_args


def test_parse_args_username_required() -> None:
    """Test that username is required."""
    with patch("sys.argv", ["script"]), pytest.raises(SystemExit):
        _parse_args()


def test_parse_args_with_username() -> None:
    """Test parsing with valid username."""
    with patch("sys.argv", ["script", "--username", "testuser"]):
        args = _parse_args()
        assert args.username == "testuser"


# Test _get_output_dir


def test_get_output_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default output directory."""
    monkeypatch.delenv("INSTAGRAM_DATA_DIR", raising=False)
    result = _get_output_dir("testuser")
    assert result == Path("data/testuser")


def test_get_output_dir_with_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test output directory with env var."""
    monkeypatch.setenv("INSTAGRAM_DATA_DIR", "/custom/path")
    result = _get_output_dir("testuser")
    assert result == Path("/custom/path/testuser")


# Test _collect_comments


def test_collect_comments_empty(mock_post: MagicMock) -> None:
    """Test collecting comments from post with no comments."""
    mock_post.get_comments.return_value = []

    comments, error = _collect_comments(mock_post)

    assert comments == []
    assert error is None


def test_collect_comments_with_comments(
    mocker: pytest.MockFixture,
    mock_post: MagicMock,
    mock_comment: MagicMock,
) -> None:
    """Test collecting comments from post."""
    mock_post.get_comments.return_value = [mock_comment]

    comments, error = _collect_comments(mock_post)

    assert len(comments) == 1
    assert comments[0]["id"] == "12345"
    assert error is None


def test_collect_comments_with_replies(
    mocker: pytest.MockFixture,
    mock_post: MagicMock,
    mock_comment: MagicMock,
    mock_reply: MagicMock,
) -> None:
    """Test collecting comments with replies."""
    mock_comment.answers = [mock_reply]
    mock_post.get_comments.return_value = [mock_comment]

    comments, error = _collect_comments(mock_post)

    assert len(comments) == 2
    assert comments[0]["id"] == "12345"
    assert comments[0]["parent_id"] is None
    assert comments[1]["id"] == "12346"
    assert comments[1]["parent_id"] == "12345"
    assert error is None


def test_collect_comments_exception(
    mocker: pytest.MockFixture,
    mock_post: MagicMock,
) -> None:
    """Test handling InstaloaderException during comment collection."""
    mock_post.get_comments.side_effect = InstaloaderException("API error")

    comments, error = _collect_comments(mock_post)

    assert comments == []
    assert error == "API error"


# Test _comment_row


def test_comment_row_adds_post_shortcode(mock_comment: MagicMock) -> None:
    """Test that _comment_row adds post_shortcode."""
    result = _comment_row(mock_comment, "POST123")

    assert result["post_shortcode"] == "POST123"
    assert result["id"] == "12345"


# Test _iter_post_rows


def test_iter_post_rows_success(
    mock_instaloader: MagicMock,
    mock_profile: MagicMock,
    mock_post: MagicMock,
) -> None:
    """Test successful post iteration."""
    posts, comments, errors = _iter_post_rows(
        mock_instaloader,
        mock_profile,
        "testuser",
    )

    assert len(posts) == 1
    assert posts[0]["shortcode"] == "ABC123"
    assert posts[0]["owner_username"] == "testuser"
    assert posts[0]["post_url"] == "https://www.instagram.com/p/ABC123/"
    assert comments == []
    assert errors == []


def test_iter_post_rows_quota_warning(
    mocker: pytest.MockFixture,
    mock_instaloader: MagicMock,
    mock_profile: MagicMock,
    mock_post: MagicMock,
) -> None:
    """Test quota warning detection."""
    mock_instaloader.context.quotamessages = ["Rate limit warning"]

    with patch(
        "instagram_scraper.workflows.profile.get_logger",
    ) as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        _iter_post_rows(mock_instaloader, mock_profile, "testuser")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[1]["extra"]["quota_message"] == "Rate limit warning"


def test_iter_post_rows_extraction_error(
    mocker: pytest.MockFixture,
    mock_instaloader: MagicMock,
    mock_profile: MagicMock,
    mock_post: MagicMock,
) -> None:
    """Test handling extraction errors."""
    mock_post.comments = 5
    mock_post.get_comments.side_effect = InstaloaderException("Comment fetch failed")

    posts, comments, errors = _iter_post_rows(
        mock_instaloader,
        mock_profile,
        "testuser",
    )

    assert len(posts) == 0
    assert len(comments) == 0
    assert len(errors) == 1
    assert errors[0]["post_shortcode"] == "ABC123"
    assert "Comment fetch failed" in errors[0]["error"]


def test_iter_post_rows_skips_when_no_comments(
    mocker: pytest.MockFixture,
    mock_instaloader: MagicMock,
    mock_profile: MagicMock,
    mock_post: MagicMock,
) -> None:
    """Test that posts with 0 reported comments skip extraction errors."""
    mock_post.comments = 0
    mock_post.get_comments.side_effect = InstaloaderException("Comment fetch failed")

    posts, comments, errors = _iter_post_rows(
        mock_instaloader,
        mock_profile,
        "testuser",
    )

    assert len(posts) == 1  # Post still included
    assert len(errors) == 0  # But no error recorded


# Test _write_posts_csv


def test_write_posts_csv(tmp_path: Path) -> None:
    """Test writing posts to CSV."""
    posts = [
        {
            "shortcode": "ABC123",
            "post_url": "https://www.instagram.com/p/ABC123/",
            "date_utc": "2024-01-15T10:30:00+00:00",
            "caption": "Test caption",
            "likes": 100,
            "comments_count_reported": 5,
            "is_video": True,
            "typename": "GraphVideo",
            "owner_username": "testuser",
            "comments": [{"id": "1", "text": "Comment"}],  # Should be excluded
        },
    ]

    csv_path = tmp_path / "posts.csv"
    _write_posts_csv(csv_path, posts)

    content = csv_path.read_text()
    assert "shortcode" in content
    assert "ABC123" in content
    assert content.count("comments") == 1


# Test _write_comments_csv


def test_write_comments_csv(tmp_path: Path) -> None:
    """Test writing comments to CSV."""
    comments = [
        {
            "post_shortcode": "ABC123",
            "id": "1",
            "parent_id": None,
            "created_at_utc": "2024-01-15T11:00:00+00:00",
            "text": "Test comment",
            "comment_like_count": 10,
            "owner_username": "user1",
            "owner_id": "100",
        },
    ]

    csv_path = tmp_path / "comments.csv"
    _write_comments_csv(csv_path, comments)

    content = csv_path.read_text()
    assert "post_shortcode" in content
    assert "id" in content
    assert "ABC123" in content
    assert "Test comment" in content


# Test _create_instaloader


def test_create_instaloader() -> None:
    """Test Instaloader configuration."""
    loader = _create_instaloader()

    assert loader.download_pictures is False
    assert loader.download_videos is False
    assert loader.download_video_thumbnails is False
    assert loader.download_geotags is False
    assert loader.download_comments is False
    assert loader.save_metadata is False
    assert loader.compress_json is False


# Test _create_dataset_dict


def test_create_dataset_dict() -> None:
    """Test dataset dictionary creation."""
    started_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    finished_at = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)

    mock_results = MagicMock()
    mock_results.posts = [{"shortcode": "1"}, {"shortcode": "2"}]
    mock_results.flat_comments = [{"id": "1"}]
    mock_results.extraction_errors = [{"error": "test"}]

    result = _create_dataset_dict("testuser", started_at, finished_at, mock_results)

    assert result["target_profile"] == "testuser"
    assert result["source_url"] == "https://www.instagram.com/testuser/?hl=en"
    assert result["started_at_utc"] == "2024-01-15T10:00:00+00:00"
    assert result["finished_at_utc"] == "2024-01-15T11:00:00+00:00"
    assert result["posts_total"] == 2
    assert result["comments_total"] == 1
    assert result["errors_count"] == 1


# Test _create_summary_dict


def test_create_summary_dict(tmp_path: Path) -> None:
    """Test summary dictionary creation."""
    finished_at = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)

    mock_results = MagicMock()
    mock_results.posts = [{"shortcode": "1"}]
    mock_results.flat_comments = [{"id": "1"}, {"id": "2"}]
    mock_results.extraction_errors = []

    result = _create_summary_dict("testuser", finished_at, tmp_path, mock_results)

    assert result["profile"] == "testuser"
    assert result["posts_extracted"] == 1
    assert result["comments_extracted"] == 2
    assert result["errors_count"] == 0
    assert result["generated_at_utc"] == "2024-01-15T11:00:00+00:00"
    assert "files" in result
    assert str(tmp_path / "instagram_dataset.json") in result["files"]["dataset_json"]


# Test _write_outputs
