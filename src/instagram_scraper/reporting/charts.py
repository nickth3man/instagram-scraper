# Copyright (c) 2026
"""Chart preparation functions for Instagram analytics dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from instagram_scraper.reporting.types import ProfileMetrics


def prepare_activity_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Create a line chart showing posting activity over time.

    Args:
        metrics: Profile metrics containing daily post counts.

    Returns
    -------
        Chart.js configuration dict for a line chart.
    """
    daily = metrics.activity.daily_posts
    dates = list(daily.keys())
    counts = list(daily.values())

    return {
        "type": "line",
        "data": {
            "labels": dates,
            "datasets": [
                {
                    "label": "Posts",
                    "data": counts,
                    "borderColor": "#6366f1",
                    "backgroundColor": "rgba(99, 102, 241, 0.1)",
                    "fill": True,
                    "tension": 0.4,
                },
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Posts per Day",
                },
            },
            "scales": {
                "y": {"beginAtZero": True},
            },
        },
    }


def prepare_engagement_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Create a line chart showing likes and comments over time.

    Args:
        metrics: Profile metrics containing engagement history.

    Returns
    -------
        Chart.js configuration dict for a multi-line chart.
    """
    return {
        "type": "line",
        "data": {
            "labels": metrics.engagement.dates,
            "datasets": [
                {
                    "label": "Likes",
                    "data": metrics.engagement.likes,
                    "borderColor": "#10b981",
                    "backgroundColor": "rgba(16, 185, 129, 0.1)",
                    "fill": False,
                },
                {
                    "label": "Comments",
                    "data": metrics.engagement.comments,
                    "borderColor": "#f59e0b",
                    "backgroundColor": "rgba(245, 158, 11, 0.1)",
                    "fill": False,
                },
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Engagement Over Time",
                },
            },
            "scales": {
                "y": {"beginAtZero": True},
            },
        },
    }


def prepare_temporal_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Create a bar chart showing posting distribution by hour.

    Args:
        metrics: Profile metrics containing hourly distribution.

    Returns
    -------
        Chart.js configuration dict for a bar chart.
    """
    hours = list(range(24))
    hourly_data = [metrics.temporal.hourly_distribution.get(h, 0) for h in range(24)]

    return {
        "type": "bar",
        "data": {
            "labels": [f"{h:02d}:00" for h in hours],
            "datasets": [
                {
                    "label": "Posts",
                    "data": hourly_data,
                    "backgroundColor": "#8b5cf6",
                },
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Posts by Hour of Day",
                },
            },
            "scales": {
                "y": {"beginAtZero": True},
            },
        },
    }


def prepare_media_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Create a doughnut chart showing media type distribution.

    Args:
        metrics: Profile metrics containing media type counts.

    Returns
    -------
        Chart.js configuration dict for a doughnut chart.
    """
    media_types = metrics.content.media_types
    labels = list(media_types.keys())
    data = list(media_types.values())

    colors = {
        "image": "#6366f1",
        "video": "#ec4899",
        "carousel": "#14b8a6",
    }

    return {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "data": data,
                    "backgroundColor": [colors.get(lbl, "#94a3b8") for lbl in labels],
                },
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Media Type Distribution",
                },
            },
        },
    }


def prepare_hashtags_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Create a horizontal bar chart showing top hashtag usage counts.

    Args:
        metrics: Profile metrics containing top hashtags data.

    Returns
    -------
        Chart.js configuration dict for a horizontal bar chart.
    """
    hashtags = metrics.content.top_hashtags[:10]
    labels = [h[0] for h in hashtags]
    data = [h[1] for h in hashtags]

    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Usage Count",
                    "data": data,
                    "backgroundColor": "#f59e0b",
                },
            ],
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Top Hashtags",
                },
            },
            "scales": {
                "x": {"beginAtZero": True},
            },
        },
    }


def prepare_comparison_chart(
    primary_metrics: ProfileMetrics,
    comparison_metrics: Sequence[tuple[str, ProfileMetrics]],
) -> dict[str, object]:
    """Create a comparison chart for the primary and peer profiles.

    Returns
    -------
        Chart.js configuration dict for comparison metrics.
    """
    labels = [primary_metrics.overview.profile_name]
    posts_data = [primary_metrics.overview.total_posts]
    likes_data = [primary_metrics.overview.avg_likes_per_post]
    comments_data = [primary_metrics.overview.avg_comments_per_post]

    for name, metrics in comparison_metrics:
        labels.append(name)
        posts_data.append(metrics.overview.total_posts)
        likes_data.append(metrics.overview.avg_likes_per_post)
        comments_data.append(metrics.overview.avg_comments_per_post)

    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Total Posts",
                    "data": posts_data,
                    "backgroundColor": "#6366f1",
                },
                {
                    "label": "Avg Likes",
                    "data": likes_data,
                    "backgroundColor": "#10b981",
                },
                {
                    "label": "Avg Comments",
                    "data": comments_data,
                    "backgroundColor": "#f59e0b",
                },
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Profile Comparison",
                },
            },
            "scales": {
                "y": {"beginAtZero": True},
            },
        },
    }


def prepare_all_chart_data(
    primary_metrics: ProfileMetrics,
    comparison_metrics: Sequence[tuple[str, ProfileMetrics]] | None,
) -> dict[str, object]:
    """Build the complete chart payload for the dashboard template.

    Returns
    -------
        Mapping of chart identifiers to Chart.js configuration payloads.
    """
    data: dict[str, object] = {
        "posting_activity": prepare_activity_chart(primary_metrics),
        "engagement_trends": prepare_engagement_chart(primary_metrics),
        "temporal_patterns": prepare_temporal_chart(primary_metrics),
        "media_distribution": prepare_media_chart(primary_metrics),
        "top_hashtags": prepare_hashtags_chart(primary_metrics),
    }

    if comparison_metrics:
        data["comparison"] = prepare_comparison_chart(
            primary_metrics,
            comparison_metrics,
        )

    return data
