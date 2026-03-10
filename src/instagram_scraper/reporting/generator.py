# Copyright (c) 2026
"""Report generation orchestrator for Instagram analytics dashboard.

This module provides the main report generation functionality,
orchestrating metric calculation and HTML template rendering.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

from instagram_scraper.logging_config import LogContext, get_logger
from instagram_scraper.reporting.metrics import (
    ProfileMetrics,
    calculate_all_metrics,
    load_ndjson_records,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_logger = get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass(frozen=True, slots=True)
class ReportConfig:
    """Configuration for report generation.

    Attributes
    ----------
    input_dir : Path
        Directory containing NDJSON data files.
    output_path : Path
        Path to write the HTML report.
    compare_dirs : list[Path] | None
        Additional directories for comparison mode.
    title : str
        Report title.
    include_charts : bool
        Whether to include Chart.js visualizations.

    """

    input_dir: Path
    output_path: Path = field(default_factory=lambda: Path("report.html"))
    compare_dirs: list[Path] | None = None
    title: str = "Instagram Analytics Report"
    include_charts: bool = True


class ReportGenerator:
    """Generates HTML analytics reports from scraped data.

    Uses Jinja2 templates and Chart.js for visualizations.
    Produces self-contained HTML files with embedded CSS/JS.
    """

    def __init__(self, config: ReportConfig) -> None:
        """Initialize report generator with configuration.

        Parameters
        ----------
        config : ReportConfig
            Report generation configuration.

        """
        self.config = config
        self._env = Environment(
            loader=FileSystemLoader(_TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate(self) -> Path:
        """Generate the HTML report.

        Returns
        -------
        Path
            Path to the generated report file.

        """
        with LogContext(report=str(self.config.output_path)):
            _logger.info("Starting report generation")

            primary_metrics = _load_metrics(self.config.input_dir)

            comparison_metrics: list[tuple[str, ProfileMetrics]] = []
            if self.config.compare_dirs:
                for comp_dir in self.config.compare_dirs:
                    profile_name = comp_dir.name
                    metrics = _load_metrics(comp_dir)
                    comparison_metrics.append((profile_name, metrics))

            chart_data = _prepare_chart_data(primary_metrics, comparison_metrics)
            html_content = self._render_html(
                primary_metrics,
                chart_data=chart_data,
                comparison_metrics=comparison_metrics,
            )
            self._write_report(html_content)

            _logger.info(
                "Report generated successfully",
                extra={"output": str(self.config.output_path)},
            )

            return self.config.output_path

    def _render_html(
        self,
        primary_metrics: ProfileMetrics,
        *,
        chart_data: dict[str, object],
        comparison_metrics: Sequence[tuple[str, ProfileMetrics]] | None = None,
    ) -> str:
        """Render the HTML report from templates.

        Parameters
        ----------
        primary_metrics : ProfileMetrics
            Metrics for the primary profile.
        chart_data : dict[str, object]
            Prepared chart configuration data.
        comparison_metrics : Sequence[tuple[str, ProfileMetrics]] | None
            Optional list of (name, metrics) tuples for comparison.

        Returns
        -------
        str
            Rendered HTML content.

        """
        template = self._env.get_template("dashboard.html")

        context = {
            "title": self.config.title,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "primary_metrics": primary_metrics,
            "comparison_metrics": comparison_metrics or [],
            "has_comparison": bool(comparison_metrics),
            "chart_data": json.dumps(chart_data),
        }

        return template.render(context)

    def _write_report(self, content: str) -> None:
        """Write the HTML report to disk.

        Parameters
        ----------
        content : str
            HTML content to write.

        """
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.output_path.write_text(content, encoding="utf-8")


def _load_metrics(input_dir: Path) -> ProfileMetrics:
    """Load and calculate metrics from NDJSON files.

    Parameters
    ----------
    input_dir : Path
        Directory containing NDJSON files.

    Returns
    -------
    ProfileMetrics
        Calculated metrics for the profile.

    """
    profile_name = input_dir.name
    records = load_ndjson_records(input_dir)

    _logger.debug(
        "Loaded records",
        extra={"count": len(records), "dir": str(input_dir)},
    )
    return calculate_all_metrics(records, profile_name=profile_name)


def _prepare_chart_data(
    primary_metrics: ProfileMetrics,
    comparison_metrics: Sequence[tuple[str, ProfileMetrics]] | None,
) -> dict[str, object]:
    """Prepare all chart configurations.

    Parameters
    ----------
    primary_metrics : ProfileMetrics
        Metrics for the primary profile.
    comparison_metrics : Sequence[tuple[str, ProfileMetrics]] | None
        Optional comparison metrics.

    Returns
    -------
    dict[str, object]
        Dictionary of chart configurations.

    """
    data: dict[str, object] = {
        "posting_activity": _prepare_activity_chart(primary_metrics),
        "engagement_trends": _prepare_engagement_chart(primary_metrics),
        "temporal_patterns": _prepare_temporal_chart(primary_metrics),
        "media_distribution": _prepare_media_chart(primary_metrics),
        "top_hashtags": _prepare_hashtags_chart(primary_metrics),
    }

    if comparison_metrics:
        data = {
            **data,
            "comparison": _prepare_comparison_chart(
                primary_metrics,
                comparison_metrics,
            ),
        }

    return data


def _prepare_activity_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Prepare posting activity chart configuration.

    Parameters
    ----------
    metrics : ProfileMetrics
        Profile metrics.

    Returns
    -------
    dict[str, object]
        Chart.js configuration.

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


def _prepare_engagement_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Prepare engagement trends chart configuration.

    Parameters
    ----------
    metrics : ProfileMetrics
        Profile metrics.

    Returns
    -------
    dict[str, object]
        Chart.js configuration.

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


def _prepare_temporal_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Prepare temporal patterns chart configuration.

    Parameters
    ----------
    metrics : ProfileMetrics
        Profile metrics.

    Returns
    -------
    dict[str, object]
        Chart.js configuration.

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


def _prepare_media_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Prepare media type distribution chart configuration.

    Parameters
    ----------
    metrics : ProfileMetrics
        Profile metrics.

    Returns
    -------
    dict[str, object]
        Chart.js configuration.

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


def _prepare_hashtags_chart(metrics: ProfileMetrics) -> dict[str, object]:
    """Prepare top hashtags chart configuration.

    Parameters
    ----------
    metrics : ProfileMetrics
        Profile metrics.

    Returns
    -------
    dict[str, object]
        Chart.js configuration.

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


def _prepare_comparison_chart(
    primary_metrics: ProfileMetrics,
    comparison_metrics: Sequence[tuple[str, ProfileMetrics]],
) -> dict[str, object]:
    """Prepare profile comparison chart configuration.

    Parameters
    ----------
    primary_metrics : ProfileMetrics
        Primary profile metrics.
    comparison_metrics : Sequence[tuple[str, ProfileMetrics]]
        Comparison profiles.

    Returns
    -------
    dict[str, object]
        Chart.js configuration.

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


def generate_report(
    input_dir: Path,
    output_path: Path,
    title: str = "Instagram Analytics Report",
) -> Path:
    """Generate an HTML analytics report.

    Parameters
    ----------
    input_dir : Path
        Directory containing NDJSON data files.
    output_path : Path
        Path to write the HTML report.
    title : str
        Report title.

    Returns
    -------
    Path
        Path to the generated report.

    """
    config = ReportConfig(
        input_dir=input_dir,
        output_path=output_path,
        title=title,
    )
    generator = ReportGenerator(config)
    return generator.generate()


def generate_comparison_report(
    input_dir: Path,
    compare_dirs: list[Path],
    output_path: Path,
    title: str = "Instagram Analytics Comparison Report",
) -> Path:
    """Generate a comparison report across multiple profiles.

    Parameters
    ----------
    input_dir : Path
        Primary directory containing NDJSON data files.
    compare_dirs : list[Path]
        Additional directories to compare.
    output_path : Path
        Path to write the HTML report.
    title : str
        Report title.

    Returns
    -------
    Path
        Path to the generated report.

    """
    config = ReportConfig(
        input_dir=input_dir,
        output_path=output_path,
        compare_dirs=compare_dirs,
        title=title,
    )
    generator = ReportGenerator(config)
    return generator.generate()
