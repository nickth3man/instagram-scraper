# Copyright (c) 2026
"""CLI helpers for the package entrypoint."""

import typer

from instagram_scraper.pipeline import run_pipeline

app = typer.Typer(help="Unified one-shot Instagram scraping CLI.")
scrape_app = typer.Typer()
app.add_typer(scrape_app, name="scrape")


@scrape_app.command("profile")
def scrape_profile(username: str = typer.Option(..., "--username")) -> None:
    """Run unified profile scraping.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(run_pipeline("profile", username=username))


@scrape_app.command("url")
def scrape_url(post_url: str = typer.Option(..., "--post-url")) -> None:
    """Run unified direct-URL scraping.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(run_pipeline("url", post_url=post_url))


@scrape_app.command("hashtag")
def scrape_hashtag(
    hashtag: str = typer.Option(..., "--hashtag"),
    limit: int | None = typer.Option(None, "--limit"),
    cookie_header: str = typer.Option("", "--cookie-header"),
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
            has_auth=bool(cookie_header),
        ),
    )


@scrape_app.command("location")
def scrape_location(
    location: str = typer.Option(..., "--location"),
    limit: int | None = typer.Option(None, "--limit"),
    cookie_header: str = typer.Option("", "--cookie-header"),
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
            has_auth=bool(cookie_header),
        ),
    )


@scrape_app.command("followers")
def scrape_followers(
    cookie_header: str = typer.Option("", "--cookie-header"),
) -> None:
    """Run unified followers discovery.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(run_pipeline("followers", has_auth=bool(cookie_header)))


@scrape_app.command("following")
def scrape_following(
    cookie_header: str = typer.Option("", "--cookie-header"),
) -> None:
    """Run unified following discovery.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(run_pipeline("following", has_auth=bool(cookie_header)))


@scrape_app.command("likers")
def scrape_likers(
    cookie_header: str = typer.Option("", "--cookie-header"),
) -> None:
    """Run unified likers discovery.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(run_pipeline("likers", has_auth=bool(cookie_header)))


@scrape_app.command("commenters")
def scrape_commenters(
    cookie_header: str = typer.Option("", "--cookie-header"),
) -> None:
    """Run unified commenters discovery.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(run_pipeline("commenters", has_auth=bool(cookie_header)))


@scrape_app.command("stories")
def scrape_stories(
    cookie_header: str = typer.Option("", "--cookie-header"),
) -> None:
    """Run unified stories scraping.

    Raises
    ------
    Exit
        Raised with the pipeline exit code.

    """
    raise typer.Exit(run_pipeline("stories", has_auth=bool(cookie_header)))


def main() -> None:
    """Run the Typer application."""
    app()
