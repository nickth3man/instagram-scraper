# Copyright (c) 2026
"""Parquet format exporter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from instagram_scraper.exporters.base import Exporter

if TYPE_CHECKING:
    import pandas as pd


class ParquetExporter(Exporter):
    """Export DataFrame to Parquet format.

    This exporter writes DataFrames to Parquet files using pyarrow
    as the engine. Parquet is a columnar storage format that provides
    efficient compression and encoding.

    Attributes
    ----------
    output_path : Path
        The destination file path for the exported Parquet file.

    """

    def export(self, df: pd.DataFrame) -> int:
        """Export the DataFrame to Parquet format.

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
        df.to_parquet(
            self.output_path,
            index=False,
            engine="pyarrow",
            compression="snappy",
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
        return "Parquet"

    @classmethod
    def file_extension(cls) -> str:
        """Return the file extension for this format.

        Returns
        -------
        str
            The file extension without leading dot.

        """
        return "parquet"
