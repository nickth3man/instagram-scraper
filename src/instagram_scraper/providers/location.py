# Copyright (c) 2026
"""Provider for location discovery mode."""

from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.base import build_run_summary


class LocationScrapeProvider:
    """Resolve location seed targets for downstream scraping."""

    @staticmethod
    def resolve_targets(
        *,
        location: str,
        limit: int | None,
    ) -> list[TargetRecord]:
        """Return placeholder location targets.

        Returns
        -------
        list[TargetRecord]
            Synthetic location targets for the requested limit.

        """
        count = 1 if limit is None else max(1, limit)
        return [
            TargetRecord(
                provider="http",
                target_kind="location_post",
                target_value=f"{location}:{index}",
            )
            for index in range(count)
        ]

    @staticmethod
    def run(
        *,
        location: str,
        limit: int | None = None,
        **_: object,
    ) -> RunSummary:
        """Return a normalized summary for a location scrape.

        Returns
        -------
        RunSummary
            A normalized summary for the location discovery run.

        """
        LocationScrapeProvider.resolve_targets(location=location, limit=limit)
        return build_run_summary("location")
