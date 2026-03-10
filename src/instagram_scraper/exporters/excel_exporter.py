# Copyright (c) 2026
"""Excel format exporter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from instagram_scraper.exporters.base import Exporter

if TYPE_CHECKING:
    import pandas as pd


class ExcelExporter(Exporter):
    """Export DataFrame to Excel format.

    This exporter writes DataFrames to Excel files using openpyxl
    as the engine. It includes column headers and auto-adjusts column
    widths where possible.

    Attributes
    ----------
    output_path : Path
        The destination file path for the exported Excel file.

    """

    def export(self, df: pd.DataFrame) -> int:
        """Export the DataFrame to Excel format.

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
        df.to_excel(
            self.output_path,
            index=False,
            engine="openpyxl",
            sheet_name="Data",
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
        return "Excel"

    @classmethod
    def file_extension(cls) -> str:
        """Return the file extension for this format.

        Returns
        -------
        str
            The file extension without leading dot.

        """
        return "xlsx"
