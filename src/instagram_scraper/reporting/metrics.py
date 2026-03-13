# Copyright (c) 2026
"""Metric calculation functions for Instagram scraper analytics.

This module provides functions to calculate various metrics from
scraped Instagram data stored in NDJSON format.
"""

from __future__ import annotations

import json
from datetime import datetime
from operator import itemgetter
from typing import TYPE_CHECKING, cast, overload

from instagram_scraper.reporting.types import (
    DAY_NAMES,
    ActivityMetrics,
    ContentMetrics,
    EngagementMetrics,
    OverviewMetrics,
    ProfileMetrics,
    TemporalMetrics,
)

if TYPE_CHECKING:
    from pathlib import Path


def _extract_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = f"{value[:-1]}+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _get_week_identifier(dt: datetime) -> str:
    iso_calendar = dt.isocalendar()
    return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"


@overload
def _increment_counter(counter: dict[str, int], key: str, amount: int = 1) -> None: ...


@overload
def _increment_counter(counter: dict[int, int], key: int, amount: int = 1) -> None: ...


def _increment_counter(
    counter: dict[str, int] | dict[int, int],
    key: str | int,
    amount: int = 1,
) -> None:
    if isinstance(key, str):
        string_counter = cast("dict[str, int]", counter)
        string_counter[key] = string_counter.get(key, 0) + amount
        return
    int_counter = cast("dict[int, int]", counter)
    int_counter[key] = int_counter.get(key, 0) + amount


def _iter_records_with_datetime(
    records: list[dict[str, object]],
) -> list[tuple[dict[str, object], datetime]]:
    dated_records: list[tuple[dict[str, object], datetime]] = []
    for record in records:
        taken_at = record.get("taken_at_utc")
        if not isinstance(taken_at, str):
            continue
        dt = _parse_iso_datetime(taken_at)
        if dt is not None:
            dated_records.append((record, dt))
    return dated_records


def _empty_hourly_distribution() -> dict[int, int]:
    return dict.fromkeys(range(24), 0)


def _empty_daily_distribution() -> dict[str, int]:
    return dict.fromkeys(DAY_NAMES, 0)


def _extract_hashtags(text: str | None) -> list[str]:
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
    """Load NDJSON records from all `.ndjson` files in a directory.

    Returns
    -------
        List of decoded record dictionaries.
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
    """Calculate overview totals for a profile dataset.

    Returns
    -------
        Aggregate overview metrics for the supplied records.
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
        if isinstance(taken_at, str):
            dt = _parse_iso_datetime(taken_at)
            if dt is not None:
                dates.append(dt)

    date_range_start = min(dates, default=None)
    date_range_end = max(dates, default=None)

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
    """Calculate daily likes and comments for the dataset.

    Returns
    -------
        Engagement metrics grouped by date.
    """
    daily_likes: dict[str, int] = {}
    daily_comments: dict[str, int] = {}

    for record, dt in _iter_records_with_datetime(records):
        date_str = dt.strftime("%Y-%m-%d")

        _increment_counter(
            daily_likes,
            date_str,
            _extract_int(record.get("like_count", 0)),
        )
        _increment_counter(
            daily_comments,
            date_str,
            _extract_int(record.get("comment_count", 0)),
        )

    dates = sorted(daily_likes.keys())
    likes = [daily_likes[d] for d in dates]
    comments = [daily_comments[d] for d in dates]
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
    """Calculate hourly and weekday posting distributions.

    Returns
    -------
        Temporal metrics derived from valid timestamps.
    """
    hourly_distribution = _empty_hourly_distribution()
    daily_distribution = _empty_daily_distribution()

    for _, dt in _iter_records_with_datetime(records):
        _increment_counter(hourly_distribution, dt.hour)
        _increment_counter(daily_distribution, dt.strftime("%A"))

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
    """Calculate hashtag, mention, caption, and media-type metrics.

    Returns
    -------
        Content metrics derived from captions and media metadata.
    """
    hashtag_counts: dict[str, int] = {}
    media_types: dict[str, int] = {}
    caption_lengths: list[int] = []
    posts_with_hashtags = 0
    posts_with_mentions = 0

    for record in records:
        caption = record.get("caption")
        if caption and isinstance(caption, str):
            if hashtags := _extract_hashtags(caption):
                posts_with_hashtags += 1
                for tag in hashtags:
                    _increment_counter(hashtag_counts, tag)
            mentions = _extract_mentions(caption)
            if mentions:
                posts_with_mentions += 1

            caption_lengths.append(len(caption))

        media_type = record.get("media_type")
        if media_type and isinstance(media_type, str):
            _increment_counter(media_types, media_type)
        elif record.get("is_video") is True:
            _increment_counter(media_types, "video")
        else:
            _increment_counter(media_types, "image")

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
    """Calculate daily, weekly, and monthly posting activity.

    Returns
    -------
        Activity counts grouped by day, week, and month.
    """
    daily_posts: dict[str, int] = {}
    weekly_posts: dict[str, int] = {}
    monthly_posts: dict[str, int] = {}

    for _, dt in _iter_records_with_datetime(records):
        date_str = dt.strftime("%Y-%m-%d")
        _increment_counter(daily_posts, date_str)

        week_id = _get_week_identifier(dt)
        _increment_counter(weekly_posts, week_id)

        month_str = dt.strftime("%Y-%m")
        _increment_counter(monthly_posts, month_str)

    return ActivityMetrics(
        daily_posts=daily_posts,
        weekly_posts=weekly_posts,
        monthly_posts=monthly_posts,
    )


def calculate_all_metrics(
    records: list[dict[str, object]],
    profile_name: str = "Unknown",
) -> ProfileMetrics:
    """Calculate the full analytics bundle for a profile dataset.

    Returns
    -------
        Complete profile metrics assembled from all sub-calculations.
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
