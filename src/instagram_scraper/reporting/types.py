# Copyright (c) 2026
"""Dataclasses for Instagram analytics metrics.

This module provides data container classes for metrics used in
the reporting and analytics dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


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
