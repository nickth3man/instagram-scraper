# Copyright (c) 2026
"""Tests for data export functionality."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from instagram_scraper.export_filters import (
    DATA_TYPE_FILES,
    ExportFilter,
    apply_filters,
    load_ndjson_to_dataframe,
    run_export,
)
from instagram_scraper.exporters import (
    CsvExporter,
    ExcelExporter,
    ParquetExporter,
    get_exporter,
)

SAMPLE_POSTS = [
    {
        "provider": "test",
        "target_kind": "profile",
        "shortcode": "abc123",
        "post_url": "https://instagram.com/p/abc123/",
        "owner_username": "test_user",
        "taken_at_utc": "2024-01-15T10:30:00",
    },
    {
        "provider": "test",
        "target_kind": "profile",
        "shortcode": "def456",
        "post_url": "https://instagram.com/p/def456/",
        "owner_username": "other_user",
        "taken_at_utc": "2024-02-20T15:45:00",
    },
]

SAMPLE_COMMENTS = [
    {
        "provider": "test",
        "target_kind": "comment",
        "comment_id": "comment1",
        "post_shortcode": "abc123",
        "owner_username": "commenter1",
        "text": "Great post!",
        "taken_at_utc": "2024-01-16T12:00:00",
    },
    {
        "provider": "test",
        "target_kind": "comment",
        "comment_id": "comment2",
        "post_shortcode": "abc123",
        "owner_username": "commenter2",
        "text": "Nice content",
        "taken_at_utc": "2024-01-17T08:30:00",
    },
]


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_data_dir(temp_dir: Path) -> Path:
    data_dir = temp_dir / "sample_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    posts_file = data_dir / DATA_TYPE_FILES["posts"]
    with posts_file.open("w", encoding="utf-8") as f:
        for post in SAMPLE_POSTS:
            f.write(json.dumps(post) + "\n")

    comments_file = data_dir / DATA_TYPE_FILES["comments"]
    with comments_file.open("w", encoding="utf-8") as f:
        for comment in SAMPLE_COMMENTS:
            f.write(json.dumps(comment) + "\n")

    return data_dir


class TestLoadNdjsonToDataframe:
    def test_loads_existing_file(self, sample_data_dir: Path) -> None:
        posts_path = sample_data_dir / DATA_TYPE_FILES["posts"]
        df = load_ndjson_to_dataframe(posts_path)

        assert len(df) == 2
        assert "shortcode" in df.columns
        assert "owner_username" in df.columns

    def test_returns_empty_for_missing_file(self, temp_dir: Path) -> None:
        missing_path = temp_dir / "nonexistent.ndjson"
        df = load_ndjson_to_dataframe(missing_path)

        assert df.empty

    def test_handles_empty_file(self, temp_dir: Path) -> None:
        empty_file = temp_dir / "empty.ndjson"
        empty_file.write_text("", encoding="utf-8")

        df = load_ndjson_to_dataframe(empty_file)

        assert df.empty


class TestApplyFilters:
    def test_no_filters_applied(self, sample_data_dir: Path) -> None:
        df = load_ndjson_to_dataframe(sample_data_dir / DATA_TYPE_FILES["posts"])
        export_filter = ExportFilter()

        result = apply_filters(df, "posts", export_filter)

        assert len(result) == 2

    def test_filter_by_username(self, sample_data_dir: Path) -> None:
        df = load_ndjson_to_dataframe(sample_data_dir / DATA_TYPE_FILES["posts"])
        export_filter = ExportFilter(usernames=frozenset({"test_user"}))

        result = apply_filters(df, "posts", export_filter)

        assert len(result) == 1
        assert result.iloc[0]["owner_username"] == "test_user"

    def test_filter_by_since_date(self, sample_data_dir: Path) -> None:
        df = load_ndjson_to_dataframe(sample_data_dir / DATA_TYPE_FILES["posts"])
        export_filter = ExportFilter(since=datetime(2024, 2, 1))

        result = apply_filters(df, "posts", export_filter)

        assert len(result) == 1
        assert result.iloc[0]["shortcode"] == "def456"


class TestRunExport:
    def test_export_to_csv(self, sample_data_dir: Path, temp_dir: Path) -> None:
        output_path = temp_dir / "export.csv"
        export_filter = ExportFilter()

        result = run_export(
            input_dir=sample_data_dir,
            output_path=output_path,
            format_name="csv",
            export_filter=export_filter,
        )

        assert result.rows_exported == 4
        assert result.files_processed == 2
        assert "posts" in result.types_exported
        assert "comments" in result.types_exported
        assert output_path.exists()

        df = pd.read_csv(output_path)
        assert len(df) == 4

    def test_export_with_type_filter(
        self,
        sample_data_dir: Path,
        temp_dir: Path,
    ) -> None:
        output_path = temp_dir / "posts_only.csv"
        export_filter = ExportFilter(types=frozenset({"posts"}))

        result = run_export(
            input_dir=sample_data_dir,
            output_path=output_path,
            format_name="csv",
            export_filter=export_filter,
        )

        assert result.rows_exported == 2
        assert "posts" in result.types_exported
        assert "comments" not in result.types_exported

    def test_export_empty_directory(self, temp_dir: Path) -> None:
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        output_path = temp_dir / "empty_export.csv"
        export_filter = ExportFilter()

        result = run_export(
            input_dir=empty_dir,
            output_path=output_path,
            format_name="csv",
            export_filter=export_filter,
        )

        assert result.rows_exported == 0
        assert result.files_processed == 0


class TestGetExporter:
    def test_get_csv_exporter(self, temp_dir: Path) -> None:
        output_path = temp_dir / "test.csv"
        exporter = get_exporter("csv", output_path)

        assert isinstance(exporter, CsvExporter)

    def test_get_excel_exporter(self, temp_dir: Path) -> None:
        output_path = temp_dir / "test.xlsx"
        exporter = get_exporter("excel", output_path)

        assert isinstance(exporter, ExcelExporter)

    def test_get_parquet_exporter(self, temp_dir: Path) -> None:
        output_path = temp_dir / "test.parquet"
        exporter = get_exporter("parquet", output_path)

        assert isinstance(exporter, ParquetExporter)

    def test_invalid_format_raises(self, temp_dir: Path) -> None:
        output_path = temp_dir / "test.invalid"

        with pytest.raises(ValueError, match="Unsupported format"):
            get_exporter("invalid", output_path)


class TestCsvExporter:
    def test_export_dataframe(self, temp_dir: Path) -> None:
        output_path = temp_dir / "output.csv"
        exporter = CsvExporter(output_path)

        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        rows = exporter.export(df)

        assert rows == 3
        assert output_path.exists()

        loaded = pd.read_csv(output_path)
        assert len(loaded) == 3


class TestExcelExporter:
    def test_export_dataframe(self, temp_dir: Path) -> None:
        output_path = temp_dir / "output.xlsx"
        exporter = ExcelExporter(output_path)

        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        rows = exporter.export(df)

        assert rows == 3
        assert output_path.exists()


class TestParquetExporter:
    def test_export_dataframe(self, temp_dir: Path) -> None:
        output_path = temp_dir / "output.parquet"
        exporter = ParquetExporter(output_path)

        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        rows = exporter.export(df)

        assert rows == 3
        assert output_path.exists()

        loaded = pd.read_parquet(output_path)
        assert len(loaded) == 3
