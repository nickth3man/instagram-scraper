# Copyright (c) 2026
"""Tests for the reporting module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from instagram_scraper.reporting.generator import (
    ReportConfig,
    ReportGenerator,
    generate_comparison_report,
    generate_report,
)
from instagram_scraper.reporting.metrics import (
    ActivityMetrics,
    ContentMetrics,
    EngagementMetrics,
    OverviewMetrics,
    ProfileMetrics,
    TemporalMetrics,
    calculate_activity_metrics,
    calculate_all_metrics,
    calculate_content_metrics,
    calculate_engagement_metrics,
    calculate_overview_metrics,
    calculate_temporal_metrics,
    load_ndjson_records,
)


class TestLoadNdjsonRecords:
    """Tests for load_ndjson_records function."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test loading from empty directory."""
        result = load_ndjson_records(tmp_path)
        assert result == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test loading from nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"
        result = load_ndjson_records(nonexistent)
        assert result == []

    def test_single_file_with_data(self, tmp_path: Path) -> None:
        """Test loading single NDJSON file with valid records."""
        ndjson_file = tmp_path / "data.ndjson"
        records = [
            {"id": "1", "username": "user1"},
            {"id": "2", "username": "user2"},
        ]
        ndjson_file.write_text(
            "\n".join(json.dumps(r) for r in records),
            encoding="utf-8",
        )

        result = load_ndjson_records(tmp_path)
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"

    def test_multiple_files(self, tmp_path: Path) -> None:
        """Test loading from multiple NDJSON files."""
        file1 = tmp_path / "data1.ndjson"
        file2 = tmp_path / "data2.ndjson"
        file1.write_text('{"id": "1"}\n{"id": "2"}', encoding="utf-8")
        file2.write_text('{"id": "3"}', encoding="utf-8")
        result = load_ndjson_records(tmp_path)
        assert len(result) == 3

    def test_malformed_json_skipped(self, tmp_path: Path) -> None:
        """Test that malformed JSON lines are skipped."""
        ndjson_file = tmp_path / "data.ndjson"
        ndjson_file.write_text(
            '{"id": "1"}\nnot json\n{"id": "2"}',
            encoding="utf-8",
        )
        result = load_ndjson_records(tmp_path)
        assert len(result) == 2

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped."""
        ndjson_file = tmp_path / "data.ndjson"
        ndjson_file.write_text(
            '{"id": "1"}\n\n\n{"id": "2"}',
            encoding="utf-8",
        )
        result = load_ndjson_records(tmp_path)
        assert len(result) == 2

    def test_non_dict_records_skipped(self, tmp_path: Path) -> None:
        """Test that non-dict records are skipped."""
        ndjson_file = tmp_path / "data.ndjson"
        ndjson_file.write_text(
            '{"id": "1"}\n["list"]\n42\n{"id": "2"}',
            encoding="utf-8",
        )
        result = load_ndjson_records(tmp_path)
        assert len(result) == 2


class TestCalculateOverviewMetrics:
    """Tests for calculate_overview_metrics function."""

    def test_empty_records(self) -> None:
        """Test with empty records list."""
        result = calculate_overview_metrics([])
        assert result.total_posts == 0
        assert result.total_comments == 0
        assert result.unique_users == 0
        assert result.date_range_start is None
        assert result.date_range_end is None
        assert result.avg_likes_per_post == pytest.approx(0.0)
        assert result.avg_comments_per_post == pytest.approx(0.0)
        assert result.profile_name == "Unknown"

    def test_custom_profile_name(self) -> None:
        """Test with custom profile name."""
        result = calculate_overview_metrics([], profile_name="testuser")
        assert result.profile_name == "testuser"

    def test_with_sample_data(self) -> None:
        """Test with sample post data."""
        records: list[dict[str, object]] = [
            {
                "like_count": 100,
                "comment_count": 10,
                "owner_username": "user1",
                "taken_at_utc": "2024-01-15T10:00:00Z",
            },
            {
                "like_count": 200,
                "comment_count": 20,
                "owner_username": "user1",
                "taken_at_utc": "2024-01-20T15:00:00Z",
            },
        ]

        result = calculate_overview_metrics(records, profile_name="testuser")
        assert result.total_posts == 2
        assert result.total_comments == 30
        assert result.unique_users == 1
        assert result.avg_likes_per_post == pytest.approx(150.0)
        assert result.avg_comments_per_post == pytest.approx(15.0)
        assert result.profile_name == "testuser"
        assert result.date_range_start is not None
        assert result.date_range_end is not None

    def test_string_counts_converted(self) -> None:
        """Test that string counts are converted to int."""
        records: list[dict[str, object]] = [
            {"like_count": "100", "comment_count": "10"},
        ]
        result = calculate_overview_metrics(records)
        assert result.total_comments == 10
        assert result.avg_likes_per_post == pytest.approx(100.0)


class TestCalculateEngagementMetrics:
    """Tests for calculate_engagement_metrics function."""

    def test_empty_records(self) -> None:
        """Test with empty records."""
        result = calculate_engagement_metrics([])
        assert result.dates == []
        assert result.likes == []
        assert result.comments == []
        assert result.engagement_rate == []

    def test_with_data(self) -> None:
        """Test with sample engagement data."""
        records: list[dict[str, object]] = [
            {
                "taken_at_utc": "2024-01-15T10:00:00Z",
                "like_count": 100,
                "comment_count": 10,
            },
            {
                "taken_at_utc": "2024-01-15T12:00:00Z",
                "like_count": 50,
                "comment_count": 5,
            },
            {
                "taken_at_utc": "2024-01-16T10:00:00Z",
                "like_count": 75,
                "comment_count": 8,
            },
        ]

        result = calculate_engagement_metrics(records)
        assert len(result.dates) == 2
        assert "2024-01-15" in result.dates
        assert "2024-01-16" in result.dates
        assert result.likes[0] == 150
        assert result.comments[0] == 15


class TestCalculateTemporalMetrics:
    """Tests for calculate_temporal_metrics function."""

    def test_empty_records(self) -> None:
        """Test with empty records."""
        result = calculate_temporal_metrics([])
        assert result.hourly_distribution == dict.fromkeys(range(24), 0)
        assert result.daily_distribution == {
            "Monday": 0,
            "Tuesday": 0,
            "Wednesday": 0,
            "Thursday": 0,
            "Friday": 0,
            "Saturday": 0,
            "Sunday": 0,
        }

    def test_with_data(self) -> None:
        """Test with sample temporal data."""
        records: list[dict[str, object]] = [
            {
                "taken_at_utc": "2024-01-15T10:30:00Z",
                "like_count": 100,
                "comment_count": 10,
            },
            {
                "taken_at_utc": "2024-01-15T14:00:00Z",
                "like_count": 50,
                "comment_count": 5,
            },
            {
                "taken_at_utc": "2024-01-17T10:00:00Z",
                "like_count": 75,
                "comment_count": 8,
            },
        ]

        result = calculate_temporal_metrics(records)
        assert len(result.hourly_distribution) == 24
        assert result.hourly_distribution[10] == 2
        assert result.hourly_distribution[14] == 1
        assert len(result.daily_distribution) == 7


class TestCalculateContentMetrics:
    """Tests for calculate_content_metrics function."""

    def test_empty_records(self) -> None:
        """Test with empty records."""
        result = calculate_content_metrics([])
        assert result.top_hashtags == []
        assert result.media_types == {}
        assert result.caption_length_avg == pytest.approx(0.0)
        assert result.posts_with_hashtags == 0
        assert result.posts_with_mentions == 0

    def test_with_hashtags(self) -> None:
        """Test hashtag extraction."""
        records: list[dict[str, object]] = [
            {"caption": "Check this out! #travel #adventure"},
            {"caption": "Another post #travel #food"},
            {"caption": "No hashtags here"},
        ]

        result = calculate_content_metrics(records)
        assert len(result.top_hashtags) >= 2
        hashtags_dict = dict(result.top_hashtags)
        assert hashtags_dict.get("travel") == 2
        assert result.posts_with_hashtags == 2

    def test_with_mentions(self) -> None:
        """Test mention extraction."""
        records: list[dict[str, object]] = [
            {"caption": "Thanks @user1 for the idea!"},
            {"caption": "No mentions here"},
            {"caption": "Cc @user2 @user3"},
        ]

        result = calculate_content_metrics(records)
        assert result.posts_with_mentions == 2

    def test_media_type_detection(self) -> None:
        """Test media type detection."""
        records: list[dict[str, object]] = [
            {"media_type": "image"},
            {"media_type": "video"},
            {"is_video": True},
            {},
        ]

        result = calculate_content_metrics(records)
        assert result.media_types.get("image") == 2
        assert result.media_types.get("video") == 2


class TestCalculateActivityMetrics:
    """Tests for calculate_activity_metrics function."""

    def test_empty_records(self) -> None:
        """Test with empty records."""
        result = calculate_activity_metrics([])
        assert result.daily_posts == {}
        assert result.weekly_posts == {}
        assert result.monthly_posts == {}

    def test_with_data(self) -> None:
        """Test with sample activity data."""
        records: list[dict[str, object]] = [
            {"taken_at_utc": "2024-01-15T10:00:00Z"},
            {"taken_at_utc": "2024-01-15T14:00:00Z"},
            {"taken_at_utc": "2024-01-20T10:00:00Z"},
            {"taken_at_utc": "2024-02-01T10:00:00Z"},
        ]

        result = calculate_activity_metrics(records)
        assert result.daily_posts.get("2024-01-15") == 2
        assert result.daily_posts.get("2024-01-20") == 1
        assert "2024-01" in result.monthly_posts
        assert "2024-02" in result.monthly_posts

    def test_invalid_timestamps_are_skipped_consistently(self) -> None:
        """Test invalid timestamps are ignored across temporal aggregations."""
        records: list[dict[str, object]] = [
            {"taken_at_utc": "2024-01-15T10:00:00Z", "like_count": 10},
            {"taken_at_utc": "not-a-date", "like_count": 99},
            {"taken_at_utc": None, "like_count": 42},
        ]

        engagement = calculate_engagement_metrics(records)
        temporal = calculate_temporal_metrics(records)
        activity = calculate_activity_metrics(records)

        assert engagement.dates == ["2024-01-15"]
        assert engagement.likes == [10]
        assert temporal.hourly_distribution[10] == 1
        assert activity.daily_posts == {"2024-01-15": 1}


class TestCalculateAllMetrics:
    """Tests for calculate_all_metrics function."""

    def test_empty_records(self) -> None:
        """Test with empty records."""
        result = calculate_all_metrics([])
        assert isinstance(result, ProfileMetrics)
        assert isinstance(result.overview, OverviewMetrics)
        assert isinstance(result.engagement, EngagementMetrics)
        assert isinstance(result.temporal, TemporalMetrics)
        assert isinstance(result.content, ContentMetrics)
        assert isinstance(result.activity, ActivityMetrics)

    def test_with_sample_data(self) -> None:
        """Test with sample data."""
        records: list[dict[str, object]] = [
            {
                "taken_at_utc": "2024-01-15T10:00:00Z",
                "like_count": 100,
                "comment_count": 10,
                "caption": "Test #hashtag",
                "owner_username": "testuser",
            },
        ]

        result = calculate_all_metrics(records, profile_name="testuser")
        assert result.overview.total_posts == 1
        assert result.overview.profile_name == "testuser"
        assert len(result.content.top_hashtags) == 1


class TestReportConfig:
    """Tests for ReportConfig dataclass."""

    def test_defaults(self, tmp_path: Path) -> None:
        """Test default values."""
        config = ReportConfig(input_dir=tmp_path)
        assert config.output_path == Path("report.html")
        assert config.compare_dirs is None
        assert config.title == "Instagram Analytics Report"
        assert config.include_charts is True

    def test_custom_values(self, tmp_path: Path) -> None:
        """Test custom values."""
        config = ReportConfig(
            input_dir=tmp_path / "data",
            output_path=tmp_path / "output" / "report.html",
            compare_dirs=[tmp_path / "other"],
            title="Custom Report",
            include_charts=False,
        )
        assert config.input_dir == tmp_path / "data"
        assert config.output_path == tmp_path / "output" / "report.html"
        assert config.compare_dirs == [tmp_path / "other"]
        assert config.title == "Custom Report"
        assert config.include_charts is False


class TestGenerateReport:
    """Tests for generate_report function."""

    def test_generates_html_file(self, tmp_path: Path) -> None:
        """Test that report generation creates an HTML file."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        ndjson_file = input_dir / "data.ndjson"
        ndjson_file.write_text(
            json.dumps(
                {
                    "taken_at_utc": "2024-01-15T10:00:00Z",
                    "like_count": 100,
                    "comment_count": 10,
                    "caption": "Test #hashtag",
                    "owner_username": "testuser",
                },
            ),
            encoding="utf-8",
        )

        output_path = tmp_path / "report.html"
        result = generate_report(input_dir, output_path, title="Test Report")

        assert result == output_path
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Test Report" in content

    def test_empty_input(self, tmp_path: Path) -> None:
        """Test report generation with empty input."""
        input_dir = tmp_path / "empty"
        input_dir.mkdir()

        output_path = tmp_path / "report.html"
        result = generate_report(input_dir, output_path)

        assert result == output_path
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content


class TestGenerateComparisonReport:
    """Tests for generate_comparison_report function."""

    def test_comparison_report(self, tmp_path: Path) -> None:
        """Test comparison report generation."""
        primary_dir = tmp_path / "primary"
        primary_dir.mkdir()
        (primary_dir / "data.ndjson").write_text(
            json.dumps(
                {
                    "taken_at_utc": "2024-01-15T10:00:00Z",
                    "like_count": 100,
                    "comment_count": 10,
                    "owner_username": "primary_user",
                },
            ),
            encoding="utf-8",
        )

        compare_dir = tmp_path / "secondary"
        compare_dir.mkdir()
        (compare_dir / "data.ndjson").write_text(
            json.dumps(
                {
                    "taken_at_utc": "2024-01-16T10:00:00Z",
                    "like_count": 200,
                    "comment_count": 20,
                    "owner_username": "secondary_user",
                },
            ),
            encoding="utf-8",
        )

        output_path = tmp_path / "comparison_report.html"
        result = generate_comparison_report(
            primary_dir,
            [compare_dir],
            output_path,
            title="Comparison Report",
        )

        assert result == output_path
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Comparison Report" in content


class TestReportGenerator:
    """Tests for ReportGenerator class."""

    def test_init(self, tmp_path: Path) -> None:
        """Test ReportGenerator initialization."""
        config = ReportConfig(input_dir=tmp_path)
        generator = ReportGenerator(config)
        assert generator.config == config

    def test_generate_creates_file(self, tmp_path: Path) -> None:
        """Test that generate creates output file."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "data.ndjson").write_text(
            json.dumps(
                {
                    "taken_at_utc": "2024-01-15T10:00:00Z",
                    "like_count": 50,
                    "comment_count": 5,
                },
            ),
            encoding="utf-8",
        )

        output_path = tmp_path / "output" / "report.html"
        config = ReportConfig(
            input_dir=input_dir,
            output_path=output_path,
        )
        generator = ReportGenerator(config)
        result = generator.generate()

        assert result == output_path
        assert output_path.exists()

    def test_generate_with_comparison(self, tmp_path: Path) -> None:
        """Test generation with comparison directories."""
        primary_dir = tmp_path / "primary"
        primary_dir.mkdir()
        (primary_dir / "data.ndjson").write_text(
            json.dumps({"like_count": 100}),
            encoding="utf-8",
        )

        compare_dir = tmp_path / "compare"
        compare_dir.mkdir()
        (compare_dir / "data.ndjson").write_text(
            json.dumps({"like_count": 200}),
            encoding="utf-8",
        )

        output_path = tmp_path / "report.html"
        config = ReportConfig(
            input_dir=primary_dir,
            output_path=output_path,
            compare_dirs=[compare_dir],
        )
        generator = ReportGenerator(config)
        result = generator.generate()
        assert result.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "chart" in content.lower() or "Chart" in content
