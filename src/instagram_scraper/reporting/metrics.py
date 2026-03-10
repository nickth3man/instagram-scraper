# Copyright (c) 2026
"""Metric calculation functions for Instagram scraper analytics.

This module provides functions to calculate various metrics from
scraped Instagram data stored in NDJSON format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from operator import itemgetter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class OverviewMetrics:
    """High-level summary metrics for a profile.

    Attributes
    ----------
    total_posts : int
        Total number of posts analyzed.
    total_comments : int
        Total number of comments across all posts.
    unique_users : int
        Number of unique users who interacted.
    date_range_start : datetime | None
        Earliest post date.
    date_range_end : datetime | None
        Latest post date.
    avg_likes_per_post : float
        Average likes per post.
    avg_comments_per_post : float
        Average comments per post.
    profile_name : str
        Name of the profile being analyzed.

    """

    total_posts: int = 0
    total_comments: int = 0
    unique_users: int = 0
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    avg_likes_per_post: float = 0.0
    avg_comments_per_post: float = 0.0
    profile_name: str = "Unknown"


@dataclass(frozen=True, slots=True)
class EngagementMetrics:
    """Engagement trend data over time.

    Attributes
    ----------
    dates : list[str]
        ISO date strings for each data point.
    likes : list[int]
        Total likes for each period.
    comments : list[int]
        Total comments for each period.
    engagement_rate : list[float]
        Engagement rate for each period.

    """

    dates: list[str] = field(default_factory=list)
    likes: list[int] = field(default_factory=list)
    comments: list[int] = field(default_factory=list)
    engagement_rate: list[float] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TemporalMetrics:
    """Temporal posting patterns.

    Attributes
    ----------
    hourly_distribution : dict[int, int]
        Posts per hour (0-23).
    daily_distribution : dict[str, int]
        Posts per day of week.
    best_posting_hour : int
        Hour with highest engagement.
    best_posting_day : str
        Day with highest engagement.

    """

    hourly_distribution: dict[int, int] = field(default_factory=dict)
    daily_distribution: dict[str, int] = field(default_factory=dict)
    best_posting_hour: int = 12
    best_posting_day: str = "Monday"


@dataclass(frozen=True, slots=True)
class ContentMetrics:
    """Content analysis metrics.

    Attributes
    ----------
    top_hashtags : list[tuple[str, int]]
        Most used hashtags with counts.
    media_types : dict[str, int]
        Distribution of media types (image, video, carousel).
    caption_length_avg : float
        Average caption length.
    posts_with_hashtags : int
        Number of posts containing hashtags.
    posts_with_mentions : int
        Number of posts containing @mentions.

    """

    top_hashtags: list[tuple[str, int]] = field(default_factory=list)
    media_types: dict[str, int] = field(default_factory=dict)
    caption_length_avg: float = 0.0
    posts_with_hashtags: int = 0
    posts_with_mentions: int = 0


@dataclass(frozen=True, slots=True)
class ActivityMetrics:
    """Posting activity over time.

    Attributes
    ----------
    daily_posts : dict[str, int]
        Posts per day (ISO date string).
    weekly_posts : dict[str, int]
        Posts per week (week identifier).
    monthly_posts : dict[str, int]
        Posts per month (YYYY-MM).

    """

    daily_posts: dict[str, int] = field(default_factory=dict)
    weekly_posts: dict[str, int] = field(default_factory=dict)
    monthly_posts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProfileMetrics:
    """Complete metrics for a single profile.

    Attributes
    ----------
    overview : OverviewMetrics
        High-level summary metrics.
    engagement : EngagementMetrics
        Engagement trend data.
    temporal : TemporalMetrics
        Temporal posting patterns.
    content : ContentMetrics
        Content analysis metrics.
    activity : ActivityMetrics
        Posting activity over time.

    """

    overview: OverviewMetrics = field(default_factory=OverviewMetrics)
    engagement: EngagementMetrics = field(default_factory=EngagementMetrics)
    temporal: TemporalMetrics = field(default_factory=TemporalMetrics)
    content: ContentMetrics = field(default_factory=ContentMetrics)
    activity: ActivityMetrics = field(default_factory=ActivityMetrics)


def _extract_int(value: object) -> int:
    """Extract an integer from a value, handling strings and ints.

    Parameters
    ----------
    value : object
        Value to extract integer from (int, str, or other).

    Returns
    -------
    int
        Extracted integer or 0 if invalid.

    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse ISO format datetime string.

    Parameters
    ----------
    value : str | None
        ISO format datetime string.

    Returns
    -------
    datetime | None
        Parsed datetime or None if invalid.

    """
    if not value:
        return None
    try:
        # Handle both with and without timezone
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _get_week_identifier(dt: datetime) -> str:
    """Get week identifier (YYYY-WXX) for a datetime.

    Parameters
    ----------
    dt : datetime
        Datetime to get week identifier for.

    Returns
    -------
    str
        Week identifier in format YYYY-WXX.

    """
    iso_calendar = dt.isocalendar()
    return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"


def _extract_hashtags(text: str | None) -> list[str]:
    """Extract hashtags from text.

    Parameters
    ----------
    text : str | None
        Text to extract hashtags from.

    Returns
    -------
    list[str]
        List of hashtags (without # prefix).

    """
    if not text:
        return []
    hashtags: list[str] = []
    in_hashtag = False
    current_hashtag: list[str] = []
    for char in text:
        if char == "#":
            if current_hashtag:
                hashtags.append("".join(current_hashtag))
            in_hashtag = True
            current_hashtag = []
        elif in_hashtag:
            if char.isalnum() or char == "_":
                current_hashtag.append(char)
            else:
                if current_hashtag:
                    hashtags.append("".join(current_hashtag))
                in_hashtag = False
                current_hashtag = []
    if current_hashtag:
        hashtags.append("".join(current_hashtag))
    return hashtags


def _extract_mentions(text: str | None) -> list[str]:
    """Extract @mentions from text.

    Parameters
    ----------
    text : str | None
        Text to extract mentions from.

    Returns
    -------
    list[str]
        List of usernames (without @ prefix).

    """
    if not text:
        return []
    mentions: list[str] = []
    in_mention = False
    current_mention: list[str] = []
    for char in text:
        if char == "@":
            if current_mention:
                mentions.append("".join(current_mention))
            in_mention = True
            current_mention = []
        elif in_mention:
            if char.isalnum() or char in "._":
                current_mention.append(char)
            else:
                if current_mention:
                    mentions.append("".join(current_mention))
                in_mention = False
                current_mention = []
    if current_mention:
        mentions.append("".join(current_mention))
    return mentions


def load_ndjson_records(input_path: Path) -> list[dict[str, object]]:
    """Load all records from NDJSON files in a directory.

    Parameters
    ----------
    input_path : Path
        Directory containing NDJSON files.

    Returns
    -------
    list[dict[str, object]]
        List of all records from all NDJSON files.

    """
    records: list[dict[str, object]] = []
    if not input_path.exists():
        return records

    for ndjson_file in input_path.glob("*.ndjson"):
        try:
            file_content = ndjson_file.read_text(encoding="utf-8")
        except OSError:
            continue

        for line in file_content.strip().split("\n"):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(record, dict):
                records.append(record)

    return records


def calculate_overview_metrics(
    records: list[dict[str, object]],
    profile_name: str = "Unknown",
) -> OverviewMetrics:
    """Calculate overview metrics from records.

    Parameters
    ----------
    records : list[dict[str, object]]
        List of record dictionaries.
    profile_name : str
        Name of the profile being analyzed.

    Returns
    -------
    OverviewMetrics
        Calculated overview metrics.

    """
    total_posts = len(records)
    unique_users: set[str] = set()
    dates: list[datetime] = []
    totals = {"comments": 0, "likes": 0}

    for record in records:
        totals["comments"] += _extract_int(record.get("comment_count", 0))
        totals["likes"] += _extract_int(record.get("like_count", 0))

        owner = record.get("owner_username")
        if owner and isinstance(owner, str):
            unique_users.add(owner)

        taken_at = record.get("taken_at_utc")
        if taken_at and isinstance(taken_at, str):
            dt = _parse_iso_datetime(taken_at)
            if dt:
                dates.append(dt)

    date_range_start = min(dates) if dates else None
    date_range_end = max(dates) if dates else None

    avg_likes_per_post = totals["likes"] / total_posts if total_posts else 0.0
    avg_comments_per_post = totals["comments"] / total_posts if total_posts else 0.0

    return OverviewMetrics(
        total_posts=total_posts,
        total_comments=totals["comments"],
        unique_users=len(unique_users),
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        avg_likes_per_post=avg_likes_per_post,
        avg_comments_per_post=avg_comments_per_post,
        profile_name=profile_name,
    )


def calculate_engagement_metrics(
    records: list[dict[str, object]],
) -> EngagementMetrics:
    """Calculate engagement metrics from records.

    Parameters
    ----------
    records : list[dict[str, object]]
        List of record dictionaries.

    Returns
    -------
    EngagementMetrics
        Calculated engagement metrics.

    """
    # Group by date (YYYY-MM-DD)
    daily_likes: dict[str, int] = {}
    daily_comments: dict[str, int] = {}

    for record in records:
        taken_at = record.get("taken_at_utc")
        if not taken_at or not isinstance(taken_at, str):
            continue
        dt = _parse_iso_datetime(taken_at)
        if not dt:
            continue
        date_str = dt.strftime("%Y-%m-%d")

        daily_likes[date_str] = daily_likes.get(date_str, 0) + _extract_int(
            record.get("like_count", 0),
        )
        daily_comments[date_str] = daily_comments.get(date_str, 0) + _extract_int(
            record.get("comment_count", 0),
        )

    dates = sorted(daily_likes.keys())
    likes = [daily_likes[d] for d in dates]
    comments = [daily_comments[d] for d in dates]

    # Engagement rate needs followers data (unavailable), return zeros
    engagement_rate = [0.0] * len(dates)

    return EngagementMetrics(
        dates=dates,
        likes=likes,
        comments=comments,
        engagement_rate=engagement_rate,
    )


def calculate_temporal_metrics(
    records: list[dict[str, object]],
) -> TemporalMetrics:
    """Calculate temporal metrics from records.

    Parameters
    ----------
    records : list[dict[str, object]]
        List of record dictionaries.

    Returns
    -------
    TemporalMetrics
        Calculated temporal metrics.

    """
    hourly_distribution = dict.fromkeys(range(24), 0)
    daily_distribution = {
        "Monday": 0,
        "Tuesday": 0,
        "Wednesday": 0,
        "Thursday": 0,
        "Friday": 0,
        "Saturday": 0,
        "Sunday": 0,
    }

    for record in records:
        taken_at = record.get("taken_at_utc")
        if not taken_at or not isinstance(taken_at, str):
            continue
        dt = _parse_iso_datetime(taken_at)
        if not dt:
            continue

        hour = dt.hour
        hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1

        day_name = dt.strftime("%A")
        daily_distribution[day_name] = daily_distribution.get(day_name, 0) + 1

    # Find best posting hour and day
    best_posting_hour = max(hourly_distribution, key=lambda k: hourly_distribution[k])
    best_posting_day = max(daily_distribution, key=lambda k: daily_distribution[k])

    return TemporalMetrics(
        hourly_distribution=hourly_distribution,
        daily_distribution=daily_distribution,
        best_posting_hour=best_posting_hour,
        best_posting_day=best_posting_day,
    )


def calculate_content_metrics(
    records: list[dict[str, object]],
) -> ContentMetrics:
    """Calculate content metrics from records.

    Parameters
    ----------
    records : list[dict[str, object]]
        List of record dictionaries.

    Returns
    -------
    ContentMetrics
        Calculated content metrics.

    """
    hashtag_counts: dict[str, int] = {}
    media_types: dict[str, int] = {}
    caption_lengths: list[int] = []
    posts_with_hashtags = 0
    posts_with_mentions = 0

    for record in records:
        # Extract hashtags from caption
        caption = record.get("caption")
        if caption and isinstance(caption, str):
            hashtags = _extract_hashtags(caption)
            if hashtags:
                posts_with_hashtags += 1
                for tag in hashtags:
                    hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
            # Count mentions
            mentions = _extract_mentions(caption)
            if mentions:
                posts_with_mentions += 1

            # Caption length
            caption_lengths.append(len(caption))

        # Media type detection
        media_type = record.get("media_type")
        if media_type and isinstance(media_type, str):
            media_types[media_type] = media_types.get(media_type, 0) + 1
        elif record.get("is_video") is True:
            media_types["video"] = media_types.get("video", 0) + 1
        else:
            # Assume image if not specified
            media_types["image"] = media_types.get("image", 0) + 1

    # Top hashtags (sorted by count)
    top_hashtags = sorted(hashtag_counts.items(), key=itemgetter(1), reverse=True)

    avg_caption_length = (
        sum(caption_lengths) / len(caption_lengths) if caption_lengths else 0.0
    )

    return ContentMetrics(
        top_hashtags=top_hashtags,
        media_types=media_types,
        caption_length_avg=avg_caption_length,
        posts_with_hashtags=posts_with_hashtags,
        posts_with_mentions=posts_with_mentions,
    )


def calculate_activity_metrics(
    records: list[dict[str, object]],
) -> ActivityMetrics:
    """Calculate activity metrics from records.

    Parameters
    ----------
    records : list[dict[str, object]]
        List of record dictionaries.

    Returns
    -------
    ActivityMetrics
        Calculated activity metrics.

    """
    daily_posts: dict[str, int] = {}
    weekly_posts: dict[str, int] = {}
    monthly_posts: dict[str, int] = {}

    for record in records:
        taken_at = record.get("taken_at_utc")
        if not taken_at or not isinstance(taken_at, str):
            continue
        dt = _parse_iso_datetime(taken_at)
        if not dt:
            continue

        date_str = dt.strftime("%Y-%m-%d")
        daily_posts[date_str] = daily_posts.get(date_str, 0) + 1

        week_id = _get_week_identifier(dt)
        weekly_posts[week_id] = weekly_posts.get(week_id, 0) + 1

        month_str = dt.strftime("%Y-%m")
        monthly_posts[month_str] = monthly_posts.get(month_str, 0) + 1

    return ActivityMetrics(
        daily_posts=daily_posts,
        weekly_posts=weekly_posts,
        monthly_posts=monthly_posts,
    )


def calculate_all_metrics(
    records: list[dict[str, object]],
    profile_name: str = "Unknown",
) -> ProfileMetrics:
    """Calculate all metrics from records.

    Parameters
    ----------
    records : list[dict[str, object]]
        List of record dictionaries.
    profile_name : str
        Name of the profile being analyzed.

    Returns
    -------
    ProfileMetrics
        Calculated metrics for the profile.

    """
    overview = calculate_overview_metrics(records, profile_name)
    engagement = calculate_engagement_metrics(records)
    temporal = calculate_temporal_metrics(records)
    content = calculate_content_metrics(records)
    activity = calculate_activity_metrics(records)

    return ProfileMetrics(
        overview=overview,
        engagement=engagement,
        temporal=temporal,
        content=content,
        activity=activity,
    )
