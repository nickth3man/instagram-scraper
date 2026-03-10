# Copyright (c) 2026
"""Abstract base class for data exporters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


class Exporter(ABC):
    """Abstract base class for data format exporters.

    Each exporter handles transforming and writing DataFrames to a specific
    file format (CSV, Excel, Parquet, etc.).

    Attributes
    ----------
    output_path : Path
        The destination file path for the exported data.

    """

    def __init__(self, output_path: Path) -> None:
        """Initialize the exporter with an output path.

        Parameters
        ----------
        output_path : Path
            The destination file path for the exported data.

        """
        self.output_path = output_path

    @abstractmethod
    def export(self, df: pd.DataFrame) -> int:
        """Export the DataFrame to the target format.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame to export.

        Returns
        -------
        int
            The number of rows exported.

        """
        ...

    @classmethod
    @abstractmethod
    def format_name(cls) -> str:
        """Return the format name for CLI help text.

        Returns
        -------
        str
            The human-readable format name.

        """
        ...

    @classmethod
    @abstractmethod
    def file_extension(cls) -> str:
        """Return the file extension for this format.

        Returns
        -------
        str
            The file extension without leading dot.

        """
        ...


def get_exporter(format_name: str, output_path: Path) -> Exporter:
    """Create an exporter based on format name.

    Parameters
    ----------
    format_name : str
        The format name (csv, excel, parquet).
    output_path : Path
        The destination file path.

    Returns
    -------
    Exporter
        An exporter instance for the specified format.

    Raises
    ------
    ValueError
        Raised when an unsupported format is requested.

    """
    # Lazy imports to avoid circular dependency
    from instagram_scraper.exporters.csv_exporter import CsvExporter  # noqa: PLC0415
    from instagram_scraper.exporters.excel_exporter import (  # noqa: PLC0415
        ExcelExporter,
    )
    from instagram_scraper.exporters.parquet_exporter import (  # noqa: PLC0415
        ParquetExporter,
    )

    exporters: dict[str, type[Exporter]] = {
        "csv": CsvExporter,
        "excel": ExcelExporter,
        "parquet": ParquetExporter,
    }

    normalized = format_name.lower().strip()
    if normalized not in exporters:
        available = ", ".join(sorted(exporters.keys()))
        message = f"Unsupported format '{format_name}'. Available formats: {available}"
        raise ValueError(message)

    exporter_class = exporters[normalized]
    return exporter_class(output_path)
