# Copyright (c) 2026
"""Tests for scrape_instagram_profile module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instagram_scraper.workflows.profile import (
    COMMENTS_CSV_FIELDNAMES,
    POSTS_CSV_FIELDNAMES,
    _iter_post_rows,
    _write_comments_csv,
    _write_outputs,
    _write_posts_csv,
    main,
    run_profile_scrape,
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


def test_write_outputs(tmp_path: Path) -> None:
    """Test writing all output files."""
    dataset = {"target_profile": "testuser", "posts": []}
    posts = [
        {
            "shortcode": "ABC123",
            "post_url": "https://www.instagram.com/p/ABC123/",
            "date_utc": "2024-01-15T10:30:00+00:00",
            "caption": "Test",
            "likes": 100,
            "comments_count_reported": 5,
            "is_video": True,
            "typename": "GraphVideo",
            "owner_username": "testuser",
        },
    ]
    comments: list[dict[str, int | str | None]] = [
        {"post_shortcode": "ABC123", "id": "1"},
    ]

    _write_outputs(tmp_path, dataset, posts, comments)

    # Check dataset JSON
    dataset_path = tmp_path / "instagram_dataset.json"
    assert dataset_path.exists()
    assert json.loads(dataset_path.read_text())["target_profile"] == "testuser"

    # Check posts CSV
    posts_path = tmp_path / "posts.csv"
    assert posts_path.exists()
    assert "ABC123" in posts_path.read_text()

    # Check comments CSV
    comments_path = tmp_path / "comments.csv"
    assert comments_path.exists()
    assert "ABC123" in comments_path.read_text()


# Test run_profile_scrape


@patch("instagram_scraper.workflows.profile.Profile")
@patch("instagram_scraper.workflows.profile._create_instaloader")
def test_run_profile_scrape_success(
    mock_create_loader: MagicMock,
    mock_profile_class: MagicMock,
    tmp_path: Path,
    mock_instaloader: MagicMock,
    mock_profile: MagicMock,
    mock_post: MagicMock,
) -> None:
    """Test successful profile scrape."""
    mock_create_loader.return_value = mock_instaloader
    mock_profile_class.from_username.return_value = mock_profile

    result = run_profile_scrape(username="testuser", output_dir=tmp_path)

    assert result["posts"] == 1
    assert result["comments"] == 0
    assert result["errors"] == 0

    # Verify files were created
    assert (tmp_path / "instagram_dataset.json").exists()
    assert (tmp_path / "posts.csv").exists()
    assert (tmp_path / "comments.csv").exists()
    assert (tmp_path / "summary.json").exists()


# Test main


@patch("instagram_scraper.workflows.profile.run_profile_scrape")
@patch("instagram_scraper.workflows.profile._parse_args")
def test_main_success(
    mock_parse_args: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """Test main function success."""
    mock_parse_args.return_value.username = "testuser"
    mock_run.return_value = {"posts": 5, "comments": 10, "errors": 0}

    main()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["posts"] == 5
    assert output["comments"] == 10


@patch("instagram_scraper.workflows.profile._parse_args")
def test_main_creates_output_dir(
    mock_parse_args: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that main calls run_profile_scrape with correct args."""
    output_dir = tmp_path / "new" / "nested" / "dir"
    mock_parse_args.return_value.username = "testuser"

    with patch(
        "instagram_scraper.workflows.profile._get_output_dir",
    ) as mock_get_dir:
        mock_get_dir.return_value = output_dir
        with patch(
            "instagram_scraper.workflows.profile.run_profile_scrape",
        ) as mock_run:
            mock_run.return_value = {"posts": 1, "comments": 0, "errors": 0}
            main()

    # Verify run_profile_scrape was called with the output directory
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args[1]
    assert call_kwargs["output_dir"] == output_dir


# Test with unicode content


def test_write_posts_csv_unicode(tmp_path: Path) -> None:
    """Test writing posts with unicode content."""
    posts = [
        {
            "shortcode": "UNI123",
            "post_url": "https://www.instagram.com/p/UNI123/",
            "date_utc": "2024-01-15T10:30:00+00:00",
            "caption": (
                "\U0001f389 Unicode test: "
                "\u00f1o\u00f1o \u4f60\u597d \u043c\u0438\u0440"
            ),
            "likes": 100,
            "comments_count_reported": 0,
            "is_video": False,
            "typename": "GraphImage",
            "owner_username": "testuser",
        },
    ]

    csv_path = tmp_path / "posts.csv"
    _write_posts_csv(csv_path, posts)

    content = csv_path.read_text(encoding="utf-8")
    assert "\U0001f389" in content
    assert "\u00f1o\u00f1o" in content
    assert "\u4f60\u597d" in content


def test_write_comments_csv_unicode(tmp_path: Path) -> None:
    """Test writing comments with unicode content."""
    comments = [
        {
            "post_shortcode": "UNI123",
            "id": "1",
            "parent_id": None,
            "created_at_utc": "2024-01-15T11:00:00+00:00",
            "text": "Emoji: \U0001f680 Special: caf\u00e9 na\u00efve",
            "comment_like_count": 5,
            "owner_username": "user\u00f1",
            "owner_id": "100",
        },
    ]

    csv_path = tmp_path / "comments.csv"
    _write_comments_csv(csv_path, comments)

    content = csv_path.read_text(encoding="utf-8")
    assert "\U0001f680" in content
    assert "caf\u00e9" in content


# Test CSV fieldnames constants


def test_posts_csv_fieldnames_complete() -> None:
    """Test that POSTS_CSV_FIELDNAMES has expected columns."""
    expected = [
        "shortcode",
        "post_url",
        "date_utc",
        "caption",
        "likes",
        "comments_count_reported",
        "is_video",
        "typename",
        "owner_username",
    ]
    assert expected == POSTS_CSV_FIELDNAMES


def test_comments_csv_fieldnames_complete() -> None:
    """Test that COMMENTS_CSV_FIELDNAMES has expected columns."""
    expected = [
        "post_shortcode",
        "id",
        "parent_id",
        "created_at_utc",
        "text",
        "comment_like_count",
        "owner_username",
        "owner_id",
    ]
    assert expected == COMMENTS_CSV_FIELDNAMES


# Test multiple posts iteration


def test_iter_post_rows_multiple_posts(
    mock_instaloader: MagicMock,
    mock_profile: MagicMock,
    mock_post: MagicMock,
) -> None:
    """Test iterating multiple posts."""
    post2 = MagicMock()
    post2.shortcode = "DEF456"
    post2.date_utc = datetime(2024, 1, 16, 10, 30, 0, tzinfo=UTC)
    post2.caption = "Second post"
    post2.likes = 50
    post2.comments = 0
    post2.is_video = False
    post2.typename = "GraphImage"
    post2.get_comments.return_value = []

    mock_profile.get_posts.return_value = [mock_post, post2]

    posts, comments, errors = _iter_post_rows(
        mock_instaloader,
        mock_profile,
        "testuser",
    )

    assert len(posts) == 2
    assert posts[0]["shortcode"] == "ABC123"
    assert posts[1]["shortcode"] == "DEF456"
