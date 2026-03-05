# Copyright (c) 2026
"""Provider for direct post URL scraping."""

from pathlib import Path

from instagram_scraper.models import RunSummary
from instagram_scraper.providers.base import build_run_summary


class UrlScrapeProvider:
    """Wrap direct-URL scraping in the unified provider interface."""

    @staticmethod
    def run(*, post_url: str, **_: object) -> RunSummary:
        """Return a normalized summary for a direct-URL scrape.

        Returns
        -------
        RunSummary
            A normalized summary rooted under the URL shortcode when available.

        """
        shortcode = post_url.rstrip("/").split("/")[-1] or "url"
        return build_run_summary("url", output_dir=Path("data") / shortcode)
