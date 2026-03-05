# Copyright (c) 2026
"""Provider for stories scraping."""

from pathlib import Path

from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.base import build_run_summary, build_target_record


class StoriesProvider:
    """Unified provider for story scraping."""

    requires_auth = True

    @staticmethod
    def resolve_targets(
        *,
        username: str | None,
        hashtag: str | None,
        limit: int | None,
    ) -> list[TargetRecord]:
        """Return normalized story targets for username or hashtag seeds.

        Returns
        -------
        list[TargetRecord]
            Synthetic story targets discovered from the selected seed.

        """
        seed_value = username if username is not None else hashtag
        seed_kind = "story_user" if username is not None else "story_hashtag"
        count = 1 if limit is None else max(1, limit)
        if seed_value is None:
            return []
        return [
            build_target_record(
                provider="http",
                target_kind=seed_kind,
                target_value=f"{seed_value}:{index}",
                mode="stories",
                provenance=[f"seed:{seed_value}"],
            )
            for index in range(count)
        ]

    @staticmethod
    def run(
        *,
        username: str | None = None,
        hashtag: str | None = None,
        limit: int | None = None,
        output_dir: Path | None = None,
        **_: object,
    ) -> RunSummary:
        """Return a normalized summary for a stories scrape.

        Returns
        -------
        RunSummary
            A normalized summary for stories scraping.

        """
        targets = StoriesProvider.resolve_targets(
            username=username,
            hashtag=hashtag,
            limit=limit,
        )
        return build_run_summary(
            "stories",
            output_dir=output_dir,
            counts={
                "processed": len(targets),
                "stories": len(targets),
                "targets": len(targets),
            },
        )
