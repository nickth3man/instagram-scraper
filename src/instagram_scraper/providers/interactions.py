# Copyright (c) 2026
"""Providers for liker/commenter discovery modes."""

from instagram_scraper.models import RunSummary
from instagram_scraper.providers.base import build_run_summary


class LikersProvider:
    """Unified provider for liker discovery."""

    @staticmethod
    def run(**_: object) -> RunSummary:
        """Return a normalized summary for a liker scrape.

        Returns
        -------
        RunSummary
            A normalized summary for liker discovery.

        """
        return build_run_summary("likers")


class CommentersProvider:
    """Unified provider for commenter discovery."""

    @staticmethod
    def run(**_: object) -> RunSummary:
        """Return a normalized summary for a commenter scrape.

        Returns
        -------
        RunSummary
            A normalized summary for commenter discovery.

        """
        return build_run_summary("commenters")
