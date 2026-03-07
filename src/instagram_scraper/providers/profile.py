# Copyright (c) 2026
"""Provider for username/profile scraping."""

from pathlib import Path

from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.base import build_run_summary, build_target_record
from instagram_scraper.scrape_instagram_profile import run_profile_scrape


class ProfileScrapeProvider:
    """Wrap profile scraping in the unified provider interface."""

    @staticmethod
    def resolve_targets(*, username: str) -> list[TargetRecord]:
        """Return the normalized seed target for a profile scrape.

        Returns
        -------
        list[TargetRecord]
            The single normalized profile target requested by the CLI.

        """
        return [
            build_target_record(
                provider="instaloader",
                target_kind="profile",
                target_value=username,
                mode="profile",
            ),
        ]

    @staticmethod
    def run(
        *,
        username: str,
        output_dir: Path | None = None,
        **_: object,
    ) -> RunSummary:
        """Return a normalized summary for a profile scrape.

        Returns
        -------
        RunSummary
            A normalized summary rooted under the requested username directory.

        """
        destination = output_dir or Path("data") / username
        result = run_profile_scrape(
            username=username,
            output_dir=destination,
        )
        return build_run_summary(
            "profile",
            output_dir=destination,
            counts={
                "processed": 1,
                "posts": _summary_int(result, "posts"),
                "comments": _summary_int(result, "comments"),
                "targets": 1,
                "errors": _summary_int(result, "errors"),
            },
        )


def _summary_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) else 0
