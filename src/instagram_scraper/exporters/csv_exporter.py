# Copyright (c) 2026
"""CSV format exporter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from instagram_scraper.exporters.base import Exporter

if TYPE_CHECKING:
    import pandas as pd


class CsvExporter(Exporter):
    """Export DataFrame to CSV format.

    This exporter writes DataFrames to CSV files with UTF-8 encoding
    and includes headers by default.

    Attributes
    ----------
    output_path : Path
        The destination file path for the exported CSV.

    """

    def export(self, df: pd.DataFrame) -> int:
        """Export the DataFrame to CSV format.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame to export.

        Returns
        -------
        int
            The number of rows exported.

        """
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(
            self.output_path,
            index=False,
            encoding="utf-8",
            date_format="%Y-%m-%d %H:%M:%S",
        )
        return len(df)

    @classmethod
    def format_name(cls) -> str:
        """Return the format name for CLI help text.

        Returns
        -------
        str
            The human-readable format name.

        """
        return "CSV"

    @classmethod
    def file_extension(cls) -> str:
        """Return the file extension for this format.

        Returns
        -------
        str
            The file extension without leading dot.

        """
        return "csv"
