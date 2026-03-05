# Copyright (c) 2026
"""Provider for follower/following discovery modes."""

from instagram_scraper.models import ModeDescriptor, RunSummary
from instagram_scraper.providers.base import build_run_summary, describe_mode


class FollowGraphProvider:
    """Describe and run follow-graph discovery modes."""

    @staticmethod
    def describe_mode(mode: str) -> ModeDescriptor:
        """Return support metadata for a follow-graph mode.

        Returns
        -------
        ModeDescriptor
            Support metadata describing the requested follow-graph mode.

        """
        return describe_mode(mode, support_tier="experimental", requires_auth=True)

    @staticmethod
    def run(*, mode: str, **_: object) -> RunSummary:
        """Return a normalized summary for a follow-graph scrape.

        Returns
        -------
        RunSummary
            A normalized summary for the requested follow-graph mode.

        """
        return build_run_summary(mode)
