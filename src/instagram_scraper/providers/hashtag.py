# Copyright (c) 2026
"""Provider for hashtag discovery mode."""

from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.base import build_run_summary


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
            TargetRecord(
                provider="http",
                target_kind="hashtag_post",
                target_value=f"{hashtag}:{index}",
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
        HashtagScrapeProvider.resolve_targets(hashtag=hashtag, limit=limit)
        return build_run_summary("hashtag")
