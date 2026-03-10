# Copyright (c) 2026
"""Data filtering utilities for export operations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from instagram_scraper.exporters.base import get_exporter

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExportFilter:
    """Configuration for filtering exported data.

    Attributes
    ----------
    types : frozenset[str] | None
        Set of data types to include (posts, comments, users, stories).
        None means include all types.
    usernames : frozenset[str] | None
        Set of usernames to filter by. None means include all usernames.
    since : datetime | None
        Only include records after this datetime.
    until : datetime | None
        Only include records before this datetime.

    """

    types: frozenset[str] | None = None
    usernames: frozenset[str] | None = None
    since: datetime | None = None
    until: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Result of an export operation.

    Attributes
    ----------
    rows_exported : int
        Total number of rows exported.
    files_processed : int
        Number of input files processed.
    output_path : Path
        Path to the output file.
    types_exported : frozenset[str]
        Set of data types that were exported.

    """

    rows_exported: int
    files_processed: int
    output_path: Path
    types_exported: frozenset[str] = field(default_factory=frozenset)


DATA_TYPE_FILES: dict[str, str] = {
    "posts": "posts.ndjson",
    "comments": "comments.ndjson",
    "users": "users.ndjson",
    "stories": "stories.ndjson",
}

DATE_COLUMNS: dict[str, str] = {
    "posts": "taken_at_utc",
    "comments": "taken_at_utc",
    "stories": "taken_at_utc",
}

USERNAME_COLUMNS: dict[str, str] = {
    "posts": "owner_username",
    "comments": "owner_username",
    "users": "username",
    "stories": "owner_username",
}


def load_ndjson_to_dataframe(path: Path) -> pd.DataFrame:
    """Load an NDJSON file into a pandas DataFrame.

    Parameters
    ----------
    path : Path
        Path to the NDJSON file.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the parsed records, or empty DataFrame if
        the file doesn't exist or is empty.

    """
    if not path.exists():
        return pd.DataFrame()

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    if not lines or (len(lines) == 1 and not lines[0]):
        return pd.DataFrame()

    records = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def apply_filters(
    df: pd.DataFrame,
    data_type: str,
    export_filter: ExportFilter,
) -> pd.DataFrame:
    """Apply export filters to a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to filter.
    data_type : str
        The type of data (posts, comments, users, stories).
    export_filter : ExportFilter
        The filter configuration to apply.

    Returns
    -------
    pd.DataFrame
        The filtered DataFrame.

    """
    if df.empty:
        return df

    result = df.copy()

    date_column = DATE_COLUMNS.get(data_type)
    if date_column and date_column in result.columns:
        if export_filter.since is not None:
            since_str = export_filter.since.isoformat()
            result = result[
                result[date_column].isna() | (result[date_column] >= since_str)
            ]
        if export_filter.until is not None:
            until_str = export_filter.until.isoformat()
            result = result[
                result[date_column].isna() | (result[date_column] <= until_str)
            ]

    username_column = USERNAME_COLUMNS.get(data_type)
    if (
        export_filter.usernames is not None
        and username_column
        and username_column in result.columns
    ):
        result = result[result[username_column].isin(export_filter.usernames)]

    return result


def run_export(
    input_dir: Path,
    output_path: Path,
    format_name: str,
    export_filter: ExportFilter,
) -> ExportResult:
    """Execute the export operation.

    Returns
    -------
    ExportResult
        Summary of the export including rows exported and files processed.

    """
    types_to_export = (
        export_filter.types
        if export_filter.types is not None
        else frozenset(DATA_TYPE_FILES.keys())
    )

    dataframes: list[tuple[str, pd.DataFrame]] = []

    for data_type in types_to_export:
        if data_type not in DATA_TYPE_FILES:
            continue

        filename = DATA_TYPE_FILES[data_type]
        file_path = input_dir / filename

        df = load_ndjson_to_dataframe(file_path)
        if df.empty:
            continue

        df = apply_filters(df, data_type, export_filter)
        if df.empty:
            continue

        df["_data_type"] = data_type
        dataframes.append((data_type, df))

    if not dataframes:
        exporter = get_exporter(format_name, output_path)
        empty_df = pd.DataFrame()
        exporter.export(empty_df)
        return ExportResult(
            rows_exported=0,
            files_processed=0,
            output_path=output_path,
            types_exported=frozenset(),
        )

    all_columns: set[str] = set()
    for _, df in dataframes:
        all_columns.update(df.columns)

    column_order = sorted(all_columns - {"_data_type"})
    column_order.insert(0, "_data_type")

    aligned_dfs: list[pd.DataFrame] = []
    for _, df in dataframes:
        for col in column_order:
            if col not in df.columns:
                df[col] = None
        aligned_dfs.append(df[column_order])

    combined_df = pd.concat(aligned_dfs, ignore_index=True)

    exporter = get_exporter(format_name, output_path)
    rows_exported = exporter.export(combined_df)

    return ExportResult(
        rows_exported=rows_exported,
        files_processed=len(dataframes),
        output_path=output_path,
        types_exported=frozenset(dt for dt, _ in dataframes),
    )
