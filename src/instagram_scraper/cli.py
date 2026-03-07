# Copyright (c) 2026
"""CLI helpers for the package entrypoint."""

from pathlib import Path
from typing import cast

import click
import typer

from instagram_scraper.pipeline import run_pipeline

app = typer.Typer(help="Unified one-shot Instagram scraping CLI.")
scrape_app = typer.Typer()
app.add_typer(scrape_app, name="scrape")

USERNAME_OPTION = typer.Option(..., "--username")
URL_OPTION = typer.Option(..., "--url", "--post-url")
HASHTAG_OPTION = typer.Option(..., "--hashtag")
LOCATION_OPTION = typer.Option(..., "--location")
INPUT_OPTION = typer.Option(..., "--input")
OUTPUT_DIR_OPTION = typer.Option(None, "--output-dir")
LIMIT_OPTION = typer.Option(None, "--limit")
POSTS_LIMIT_OPTION = typer.Option(None, "--posts-limit")
COOKIE_HEADER_OPTION = typer.Option("", "--cookie-header")
RESUME_OPTION = typer.Option(None, "--resume/--no-resume")
RESET_OUTPUT_OPTION = typer.Option(None, "--reset-output/--no-reset-output")
STORIES_USERNAME_OPTION = typer.Option(None, "--username")
STORIES_HASHTAG_OPTION = typer.Option(None, "--hashtag")
STORIES_SEED_MESSAGE = "Provide exactly one of --username or --hashtag."


@scrape_app.callback()
def configure_scrape(
    ctx: typer.Context,
    *,
    raw_captures: bool | None = typer.Option(
        None,
        "--raw-captures/--no-raw-captures",
    ),
    request_timeout: int = typer.Option(30, "--request-timeout"),
    max_retries: int = typer.Option(5, "--max-retries"),
    checkpoint_every: int = typer.Option(20, "--checkpoint-every"),
) -> None:
    """Capture shared runtime controls for scrape subcommands."""
    shared_options: dict[str, object] = {
        "raw_captures": False,
        "request_timeout": request_timeout,
        "max_retries": max_retries,
        "checkpoint_every": checkpoint_every,
    }
    if raw_captures is not None:
        shared_options["raw_captures"] = raw_captures
    ctx.obj = shared_options


def _current_context() -> typer.Context:
    return cast("typer.Context", click.get_current_context())


def _pipeline_kwargs(**kwargs: object) -> dict[str, object]:
    ctx = _current_context()
    shared = ctx.obj if isinstance(ctx.obj, dict) else {}
    return {**shared, **kwargs}


def _run(mode: str, **kwargs: object) -> None:
    raise typer.Exit(run_pipeline(mode, **_pipeline_kwargs(**kwargs)))


@scrape_app.command("profile")
def scrape_profile(
    *,
    username: str = USERNAME_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
) -> None:
    """Run unified profile scraping."""
    _run("profile", username=username, output_dir=output_dir)


@scrape_app.command("url")
def scrape_url(
    *,
    post_url: str = URL_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run unified direct-URL scraping."""
    _run(
        "url",
        post_url=post_url,
        output_dir=output_dir,
        cookie_header=cookie_header,
        has_auth=bool(cookie_header),
    )


@scrape_app.command("urls")
def scrape_urls(
    *,
    input_path: Path = INPUT_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    resume: bool | None = RESUME_OPTION,
    reset_output: bool | None = RESET_OUTPUT_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run unified multi-URL scraping."""
    _run(
        "urls",
        input_path=input_path,
        output_dir=output_dir,
        resume=bool(resume),
        reset_output=bool(reset_output),
        cookie_header=cookie_header,
        has_auth=bool(cookie_header),
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
    _run(
        "hashtag",
        hashtag=hashtag,
        limit=limit,
        output_dir=output_dir,
        cookie_header=cookie_header,
        has_auth=bool(cookie_header),
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
    _run(
        "location",
        location=location,
        limit=limit,
        output_dir=output_dir,
        cookie_header=cookie_header,
        has_auth=bool(cookie_header),
    )


@scrape_app.command("followers")
def scrape_followers(
    *,
    username: str = USERNAME_OPTION,
    limit: int | None = LIMIT_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run unified followers discovery."""
    _run(
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
    _run(
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
    _run(
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
    _run(
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
    BadParameter
        Raised when the seed options are invalid.

    """
    if (username is None) == (hashtag is None):
        raise typer.BadParameter(STORIES_SEED_MESSAGE)
    _run(
        "stories",
        username=username,
        hashtag=hashtag,
        limit=limit,
        output_dir=output_dir,
        cookie_header=cookie_header,
        has_auth=bool(cookie_header),
    )


def main() -> None:
    """Run the Typer application."""
    app()
