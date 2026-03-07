# Copyright (c) 2026
"""Providers for liker/commenter discovery modes."""

from pathlib import Path

from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.base import build_run_summary, build_target_record


class _InteractionProvider:
    """Shared provider implementation for interaction-discovery modes."""

    def __init__(self, mode: str) -> None:
        self._mode = mode

    def resolve_targets(
        self,
        *,
        username: str,
        posts_limit: int | None,
        limit: int | None,
    ) -> list[TargetRecord]:
        """Return discovered user targets for the configured interaction mode.

        Returns
        -------
        list[TargetRecord]
            Synthetic user targets discovered from the configured seed posts.

        """
        return _interaction_targets(
            mode=self._mode,
            username=username,
            posts_limit=posts_limit,
            limit=limit,
        )

    def run(
        self,
        *,
        username: str,
        posts_limit: int | None = None,
        limit: int | None = None,
        output_dir: Path | None = None,
        **_: object,
    ) -> RunSummary:
        """Return a normalized summary for the configured interaction mode.

        Returns
        -------
        RunSummary
            A normalized summary describing the interaction-discovery run.

        """
        targets = self.resolve_targets(
            username=username,
            posts_limit=posts_limit,
            limit=limit,
        )
        return build_run_summary(
            self._mode,
            output_dir=output_dir,
            counts={
                "processed": len(targets),
                "targets": len(targets),
                "users": len(targets),
            },
        )


class LikersProvider(_InteractionProvider):
    """Unified provider for liker discovery."""

    def __init__(self) -> None:
        """Initialize the liker-discovery provider."""
        super().__init__("likers")


class CommentersProvider(_InteractionProvider):
    """Unified provider for commenter discovery."""

    def __init__(self) -> None:
        """Initialize the commenter-discovery provider."""
        super().__init__("commenters")


def _interaction_targets(
    *,
    mode: str,
    username: str,
    posts_limit: int | None,
    limit: int | None,
) -> list[TargetRecord]:
    count = 1 if limit is None else max(1, limit)
    post_scope = 1 if posts_limit is None else max(1, posts_limit)
    return [
        build_target_record(
            provider="http",
            target_kind="user",
            target_value=f"{mode}:{username}:post-{post_scope}:user-{index}",
            mode=mode,
            provenance=[f"seed:{username}"],
        )
        for index in range(count)
    ]
