# Copyright (c) 2026
"""Analytics dashboard generation for Instagram scraper data.

This module provides HTML report generation from scraped NDJSON data,
including visualizations for posting activity, engagement metrics,
temporal patterns, and content analysis.

Example:
-------
>>> from instagram_scraper.reporting import generate_report
>>> generate_report(
...     input_dir=Path("data/profile1"),
...     output_path=Path("report.html"),
... )

"""

from __future__ import annotations

from instagram_scraper.reporting.generator import (
    ReportConfig,
    ReportGenerator,
    generate_comparison_report,
    generate_report,
)
from instagram_scraper.reporting.metrics import (
    ContentMetrics,
    EngagementMetrics,
    OverviewMetrics,
    TemporalMetrics,
    calculate_all_metrics,
)

__all__ = [
    "ContentMetrics",
    "EngagementMetrics",
    "OverviewMetrics",
    "ReportConfig",
    "ReportGenerator",
    "TemporalMetrics",
    "calculate_all_metrics",
    "generate_comparison_report",
    "generate_report",
]
