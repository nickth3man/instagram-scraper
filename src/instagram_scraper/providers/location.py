# Copyright (c) 2026
"""Provider for location discovery mode."""

from pathlib import Path

from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.base import build_run_summary, build_target_record


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
            build_target_record(
                provider="http",
                target_kind="location_post",
                target_value=f"{location}:{index}",
                mode="location",
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
        targets = LocationScrapeProvider.resolve_targets(
            location=location,
            limit=limit,
        )
        output_dir = _.get("output_dir")
        return build_run_summary(
            "location",
            output_dir=output_dir if isinstance(output_dir, Path) else None,
            counts={"processed": len(targets), "targets": len(targets)},
        )
