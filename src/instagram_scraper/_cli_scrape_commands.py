# Copyright (c) 2026
"""Scrape and sync command registrations for the Typer CLI."""

from pathlib import Path
from typing import Protocol

import typer

from instagram_scraper._cli_options import (
    COOKIE_HEADER_OPTION,
    HASHTAG_OPTION,
    INPUT_OPTION,
    LIMIT_OPTION,
    LOCATION_OPTION,
    OUTPUT_DIR_OPTION,
    POSTS_LIMIT_OPTION,
    STORIES_HASHTAG_OPTION,
    STORIES_SEED_MESSAGE,
    STORIES_USERNAME_OPTION,
    URL_OPTION,
    USERNAME_OPTION,
)


class RunFn(Protocol):
    """Callable wrapper used to invoke the pipeline from command handlers."""

    def __call__(self, mode: str, **kwargs: object) -> None: ...


def _extra_runtime_args(args: list[str]) -> dict[str, object]:
    runtime: dict[str, object] = {}
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"--resume", "--reset-output", "--headed"}:
            runtime[arg.removeprefix("--").replace("-", "_")] = True
            index += 1
            continue
        if arg in {"--no-resume", "--no-reset-output", "--headless"}:
            key = arg.removeprefix("--no-").replace("-", "_")
            if arg == "--headless":
                key = "headed"
            runtime[key] = False
            index += 1
            continue
        if index + 1 >= len(args):
            message = f"Missing value for {arg}"
            raise typer.BadParameter(message)
        value = args[index + 1]
        if arg == "--cookies-file":
            runtime["cookies_file"] = Path(value)
        elif arg == "--storage-state":
            runtime["storage_state"] = Path(value)
        elif arg == "--user-data-dir":
            runtime["user_data_dir"] = Path(value)
        elif arg == "--timeout-ms":
            runtime["timeout_ms"] = int(value)
        index += 2
    return runtime


def _run_with_cookie(
    run: RunFn,
    mode: str,
    *,
    output_dir: object,
    cookie_header: str,
    **kwargs: object,
) -> None:
    """Run a mode with cookie-based auth detection."""
    run(
        mode,
        output_dir=output_dir,
        cookie_header=cookie_header,
        has_auth=bool(cookie_header),
        **kwargs,
    )


def register_scrape_commands(
    scrape_app: typer.Typer,
    *,
    run: RunFn,
) -> None:
    """Register `scrape` subcommands on the provided app."""
    _register_primary_scrape_commands(scrape_app, run=run)
    _register_secondary_scrape_commands(scrape_app, run=run)


def _register_primary_scrape_commands(
    scrape_app: typer.Typer,
    *,
    run: RunFn,
) -> None:
    """Register profile, URL, hashtag, and location scrape commands."""

    @scrape_app.command("profile")
    def scrape_profile(
        *,
        username: str = USERNAME_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
    ) -> None:
        """Run unified profile scraping."""
        run("profile", username=username, output_dir=output_dir)

    @scrape_app.command(
        "url",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def scrape_url(
        ctx: typer.Context,
        *,
        post_url: str = URL_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified direct-URL scraping."""
        _run_with_cookie(
            run,
            "url",
            post_url=post_url,
            output_dir=output_dir,
            cookie_header=cookie_header,
            **_extra_runtime_args(ctx.args),
        )

    @scrape_app.command(
        "urls",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def scrape_urls(
        ctx: typer.Context,
        *,
        input_path: Path = INPUT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified multi-URL scraping."""
        runtime = _extra_runtime_args(ctx.args)
        resume = bool(runtime.pop("resume", False))
        reset_output = bool(runtime.pop("reset_output", False))
        _run_with_cookie(
            run,
            "urls",
            input_path=input_path,
            output_dir=output_dir,
            cookie_header=cookie_header,
            resume=resume,
            reset_output=reset_output,
            **runtime,
        )

    @scrape_app.command("hashtag")
    def scrape_hashtag(
        *,
        hashtag: str = HASHTAG_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified hashtag scraping."""
        _run_with_cookie(
            run,
            "hashtag",
            hashtag=hashtag,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
        )

    @scrape_app.command("location")
    def scrape_location(
        *,
        location: str = LOCATION_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified location scraping."""
        run(
            "location",
            location=location,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        )


def _register_secondary_scrape_commands(
    scrape_app: typer.Typer,
    *,
    run: RunFn,
) -> None:
    """Register discovery and stories scrape commands."""

    @scrape_app.command("followers")
    def scrape_followers(
        *,
        username: str = USERNAME_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified followers discovery."""
        run(
            "followers",
            username=username,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        )

    @scrape_app.command("following")
    def scrape_following(
        *,
        username: str = USERNAME_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified following discovery."""
        run(
            "following",
            username=username,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        )

    @scrape_app.command("likers")
    def scrape_likers(
        *,
        username: str = USERNAME_OPTION,
        posts_limit: int | None = POSTS_LIMIT_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified likers discovery."""
        run(
            "likers",
            username=username,
            posts_limit=posts_limit,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        )

    @scrape_app.command("commenters")
    def scrape_commenters(
        *,
        username: str = USERNAME_OPTION,
        posts_limit: int | None = POSTS_LIMIT_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified commenters discovery."""
        run(
            "commenters",
            username=username,
            posts_limit=posts_limit,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        )

    @scrape_app.command("stories")
    def scrape_stories(
        *,
        username: str | None = STORIES_USERNAME_OPTION,
        hashtag: str | None = STORIES_HASHTAG_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run unified stories scraping.

        Raises
        ------
        typer.BadParameter
            If neither or both username and hashtag are provided.
        """
        if (username is None) == (hashtag is None):
            raise typer.BadParameter(STORIES_SEED_MESSAGE)
        run(
            "stories",
            username=username,
            hashtag=hashtag,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        )


def register_sync_commands(sync_app: typer.Typer, *, run: RunFn) -> None:
    """Register `sync` subcommands on the provided app."""

    @sync_app.command("profile")
    def sync_profile(
        *,
        username: str = USERNAME_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
    ) -> None:
        """Run incremental sync for a profile."""
        run("sync:profile", username=username, output_dir=output_dir)

    @sync_app.command("hashtag")
    def sync_hashtag(
        *,
        hashtag: str = HASHTAG_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run incremental sync for a hashtag."""
        run(
            "sync:hashtag",
            hashtag=hashtag,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        )

    @sync_app.command("location")
    def sync_location(
        *,
        location: str = LOCATION_OPTION,
        limit: int | None = LIMIT_OPTION,
        output_dir: Path | None = OUTPUT_DIR_OPTION,
        cookie_header: str = COOKIE_HEADER_OPTION,
    ) -> None:
        """Run incremental sync for a location."""
        run(
            "sync:location",
            location=location,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        )
