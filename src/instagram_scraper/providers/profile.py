# Copyright (c) 2026
"""Provider for username/profile scraping."""

from pathlib import Path

from instagram_scraper.models import RunSummary
from instagram_scraper.providers.base import build_run_summary


class ProfileScrapeProvider:
    """Wrap profile scraping in the unified provider interface."""

    @staticmethod
    def run(*, username: str, **_: object) -> RunSummary:
        """Return a normalized summary for a profile scrape.

        Returns
        -------
        RunSummary
            A normalized summary rooted under the requested username directory.

        """
        return build_run_summary("profile", output_dir=Path("data") / username)
