# Copyright (c) 2026
"""Provider for stories scraping."""

from instagram_scraper.models import RunSummary
from instagram_scraper.providers.base import build_run_summary


class StoriesProvider:
    """Unified provider for story scraping."""

    requires_auth = True

    @staticmethod
    def run(**_: object) -> RunSummary:
        """Return a normalized summary for a stories scrape.

        Returns
        -------
        RunSummary
            A normalized summary for stories scraping.

        """
        return build_run_summary("stories")
