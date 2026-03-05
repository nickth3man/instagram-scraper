# Copyright (c) 2026
"""Provider for hashtag discovery mode."""

from pathlib import Path

from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.base import build_run_summary, build_target_record


class HashtagScrapeProvider:
    """Resolve hashtag seed targets for downstream scraping."""

    @staticmethod
    def resolve_targets(
        *,
        hashtag: str,
        limit: int | None,
    ) -> list[TargetRecord]:
        """Return placeholder hashtag targets.

        Returns
        -------
        list[TargetRecord]
            Synthetic hashtag targets for the requested limit.

        """
        count = 1 if limit is None else max(1, limit)
        return [
            build_target_record(
                provider="http",
                target_kind="hashtag_post",
                target_value=f"{hashtag}:{index}",
                mode="hashtag",
            )
            for index in range(count)
        ]

    @staticmethod
    def run(*, hashtag: str, limit: int | None = None, **_: object) -> RunSummary:
        """Return a normalized summary for a hashtag scrape.

        Returns
        -------
        RunSummary
            A normalized summary for the hashtag discovery run.

        """
        targets = HashtagScrapeProvider.resolve_targets(hashtag=hashtag, limit=limit)
        output_dir = _.get("output_dir")
        return build_run_summary(
            "hashtag",
            output_dir=output_dir if isinstance(output_dir, Path) else None,
            counts={"processed": len(targets), "targets": len(targets)},
        )
