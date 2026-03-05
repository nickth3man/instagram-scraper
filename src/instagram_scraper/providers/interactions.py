# Copyright (c) 2026
"""Providers for liker/commenter discovery modes."""

from pathlib import Path

from instagram_scraper.models import RunSummary, TargetRecord
from instagram_scraper.providers.base import build_run_summary, build_target_record


class LikersProvider:
    """Unified provider for liker discovery."""

    @staticmethod
    def resolve_targets(
        *,
        username: str,
        posts_limit: int | None,
        limit: int | None,
    ) -> list[TargetRecord]:
        """Return discovered user targets for liker discovery.

        Returns
        -------
        list[TargetRecord]
            Synthetic user targets discovered from liked seed posts.

        """
        return _interaction_targets(
            mode="likers",
            username=username,
            posts_limit=posts_limit,
            limit=limit,
        )

    @staticmethod
    def run(
        *,
        username: str,
        posts_limit: int | None = None,
        limit: int | None = None,
        output_dir: Path | None = None,
        **_: object,
    ) -> RunSummary:
        """Return a normalized summary for a liker scrape.

        Returns
        -------
        RunSummary
            A normalized summary for liker discovery.

        """
        targets = LikersProvider.resolve_targets(
            username=username,
            posts_limit=posts_limit,
            limit=limit,
        )
        return build_run_summary(
            "likers",
            output_dir=output_dir,
            counts={
                "processed": len(targets),
                "targets": len(targets),
                "users": len(targets),
            },
        )


class CommentersProvider:
    """Unified provider for commenter discovery."""

    @staticmethod
    def resolve_targets(
        *,
        username: str,
        posts_limit: int | None,
        limit: int | None,
    ) -> list[TargetRecord]:
        """Return discovered user targets for commenter discovery.

        Returns
        -------
        list[TargetRecord]
            Synthetic user targets discovered from commented seed posts.

        """
        return _interaction_targets(
            mode="commenters",
            username=username,
            posts_limit=posts_limit,
            limit=limit,
        )

    @staticmethod
    def run(
        *,
        username: str,
        posts_limit: int | None = None,
        limit: int | None = None,
        output_dir: Path | None = None,
        **_: object,
    ) -> RunSummary:
        """Return a normalized summary for a commenter scrape.

        Returns
        -------
        RunSummary
            A normalized summary for commenter discovery.

        """
        targets = CommentersProvider.resolve_targets(
            username=username,
            posts_limit=posts_limit,
            limit=limit,
        )
        return build_run_summary(
            "commenters",
            output_dir=output_dir,
            counts={
                "processed": len(targets),
                "targets": len(targets),
                "users": len(targets),
            },
        )


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
