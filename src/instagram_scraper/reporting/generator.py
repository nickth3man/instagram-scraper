# Copyright (c) 2026
"""Report generation orchestrator for the Instagram analytics dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

from instagram_scraper.infrastructure.logging import LogContext, get_logger
from instagram_scraper.reporting.charts import prepare_all_chart_data
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
        Directory containing scraped post data.
    output_path : Path
        Path where the report will be written.
    compare_dirs : list[Path] | None
        Optional list of directories to compare against.
    title : str
        Title shown in the dashboard.
    include_charts : bool
        Whether chart payloads should be included in the rendered report.
    """

    input_dir: Path
    output_path: Path = Path("report.html")
    compare_dirs: list[Path] | None = None
    title: str = "Instagram Analytics Report"
    include_charts: bool = True


class ReportGenerator:
    """Render an analytics report from scraped NDJSON data."""

    __slots__ = ("_env", "config")

    def __init__(self, config: ReportConfig) -> None:
        """Initialize the generator with report configuration."""
        self.config = config
        self._env = Environment(
            loader=FileSystemLoader(_TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate(self) -> Path:
        """Generate the configured report and return its output path.

        Returns
        -------
            Path to the written HTML report.
        """
        with LogContext(output=str(self.config.output_path)):
            primary_metrics = _load_metrics(self.config.input_dir)
            comparison_metrics = (
                [
                    (compare_dir.name, _load_metrics(compare_dir))
                    for compare_dir in self.config.compare_dirs
                ]
                if self.config.compare_dirs
                else []
            )

            chart_metrics: Sequence[tuple[str, ProfileMetrics]] | None = None
            if comparison_metrics:
                chart_metrics = comparison_metrics
            chart_data = (
                prepare_all_chart_data(primary_metrics, chart_metrics)
                if self.config.include_charts
                else {}
            )
            html_content = self._render_html(
                primary_metrics,
                chart_data=chart_data,
                comparison_metrics=comparison_metrics,
            )
            self._write_report(html_content)

            _logger.info("Report generated successfully")
            return self.config.output_path

    def _render_html(
        self,
        primary_metrics: ProfileMetrics,
        *,
        chart_data: dict[str, object],
        comparison_metrics: Sequence[tuple[str, ProfileMetrics]] | None = None,
    ) -> str:
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
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.output_path.write_text(content, encoding="utf-8")


def _load_metrics(input_dir: Path) -> ProfileMetrics:
    profile_name = input_dir.name
    records = load_ndjson_records(input_dir)
    _logger.debug(
        "Loaded records",
        extra={"count": len(records), "dir": str(input_dir)},
    )
    return calculate_all_metrics(records, profile_name=profile_name)


def generate_report(
    input_dir: Path,
    output_path: Path,
    title: str = "Instagram Analytics Report",
) -> Path:
    """Generate a report for a single input directory.

    Returns
    -------
        Path to the written HTML report.
    """
    config = ReportConfig(
        input_dir=input_dir,
        output_path=output_path,
        title=title,
    )
    return ReportGenerator(config).generate()


def generate_comparison_report(
    input_dir: Path,
    compare_dirs: list[Path],
    output_path: Path,
    title: str = "Instagram Analytics Comparison Report",
) -> Path:
    """Generate a report that compares the primary input against peers.

    Returns
    -------
        Path to the written HTML report.
    """
    config = ReportConfig(
        input_dir=input_dir,
        output_path=output_path,
        compare_dirs=compare_dirs,
        title=title,
    )
    return ReportGenerator(config).generate()
