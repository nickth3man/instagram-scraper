# Copyright (c) 2026
"""Provider for follower/following discovery modes."""

from pathlib import Path

from instagram_scraper.models import ModeDescriptor, RunSummary, TargetRecord
from instagram_scraper.providers.base import (
    build_run_summary,
    build_target_record,
    describe_mode,
)


class FollowGraphProvider:
    """Describe and run follow-graph discovery modes."""

    @staticmethod
    def resolve_targets(
        *,
        mode: str,
        username: str,
        limit: int | None,
    ) -> list[TargetRecord]:
        """Return discovered user targets for a follow-graph mode.

        Returns
        -------
        list[TargetRecord]
            Synthetic user targets discovered from the follow-graph seed.

        """
        count = 1 if limit is None else max(1, limit)
        return [
            build_target_record(
                provider="http",
                target_kind="user",
                target_value=f"{mode}:{username}:{index}",
                mode=mode,
                provenance=[f"seed:{username}"],
            )
            for index in range(count)
        ]

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
    def run(
        *,
        mode: str,
        username: str,
        limit: int | None = None,
        output_dir: Path | None = None,
        **_: object,
    ) -> RunSummary:
        """Return a normalized summary for a follow-graph scrape.

        Returns
        -------
        RunSummary
            A normalized summary for the requested follow-graph mode.

        """
        targets = FollowGraphProvider.resolve_targets(
            mode=mode,
            username=username,
            limit=limit,
        )
        return build_run_summary(
            mode,
            output_dir=output_dir,
            counts={
                "processed": len(targets),
                "targets": len(targets),
                "users": len(targets),
            },
        )
