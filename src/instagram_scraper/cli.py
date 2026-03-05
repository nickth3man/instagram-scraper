# Copyright (c) 2026
"""CLI helpers for the package entrypoint."""

from pathlib import Path

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


@scrape_app.command("profile")
def scrape_profile(
    *,
    username: str = USERNAME_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
) -> None:
    """Run unified profile scraping.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline("profile", username=username, output_dir=output_dir),
    )


@scrape_app.command("url")
def scrape_url(
    *,
    post_url: str = URL_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run unified direct-URL scraping.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline(
            "url",
            post_url=post_url,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
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
    """Run unified multi-URL scraping.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline(
            "urls",
            input_path=input_path,
            output_dir=output_dir,
            resume=bool(resume),
            reset_output=bool(reset_output),
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
    )


@scrape_app.command("hashtag")
def scrape_hashtag(
    *,
    hashtag: str = HASHTAG_OPTION,
    limit: int | None = LIMIT_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run unified hashtag scraping.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline(
            "hashtag",
            hashtag=hashtag,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
    )


@scrape_app.command("location")
def scrape_location(
    *,
    location: str = LOCATION_OPTION,
    limit: int | None = LIMIT_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run unified location scraping.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline(
            "location",
            location=location,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
    )


@scrape_app.command("followers")
def scrape_followers(
    *,
    username: str = USERNAME_OPTION,
    limit: int | None = LIMIT_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run unified followers discovery.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline(
            "followers",
            username=username,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
    )


@scrape_app.command("following")
def scrape_following(
    *,
    username: str = USERNAME_OPTION,
    limit: int | None = LIMIT_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run unified following discovery.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline(
            "following",
            username=username,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
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
    """Run unified likers discovery.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline(
            "likers",
            username=username,
            posts_limit=posts_limit,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
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
    """Run unified commenters discovery.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(
        run_pipeline(
            "commenters",
            username=username,
            posts_limit=posts_limit,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
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
    Exit
        Raised with the pipeline exit code.

    """
    if (username is None) == (hashtag is None):
        message = STORIES_SEED_MESSAGE
        raise typer.BadParameter(message)
    raise typer.Exit(
        run_pipeline(
            "stories",
            username=username,
            hashtag=hashtag,
            limit=limit,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
    )


def main() -> None:
    """Run the Typer application."""
    app()
