# Copyright (c) 2026
"""Tests for scrape_instagram_profile module."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from instagram_scraper.workflows.profile import (
    COMMENTS_CSV_FIELDNAMES,
    POSTS_CSV_FIELDNAMES,
    _iter_post_rows,
    _write_comments_csv,
    _write_posts_csv,
)

# Fixtures


def test_write_posts_csv_unicode(tmp_path: Path) -> None:
    """Test writing posts with unicode content."""
    posts = [
        {
            "shortcode": "UNI123",
            "post_url": "https://www.instagram.com/p/UNI123/",
            "date_utc": "2024-01-15T10:30:00+00:00",
            "caption": "🎉 Unicode test: ñoño 你好 мир",
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
    assert "🎉" in content
    assert "ñoño" in content
    assert "你好" in content


def test_write_comments_csv_unicode(tmp_path: Path) -> None:
    """Test writing comments with unicode content."""
    comments = [
        {
            "post_shortcode": "UNI123",
            "id": "1",
            "parent_id": None,
            "created_at_utc": "2024-01-15T11:00:00+00:00",
            "text": "Emoji: 🚀 Special: café naïve",
            "comment_like_count": 5,
            "owner_username": "userñ",
            "owner_id": "100",
        },
    ]

    csv_path = tmp_path / "comments.csv"
    _write_comments_csv(csv_path, comments)

    content = csv_path.read_text(encoding="utf-8")
    assert "🚀" in content
    assert "café" in content


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
