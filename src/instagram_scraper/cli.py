# Copyright (c) 2026
"""CLI helpers for the package entrypoint."""

import typer

app = typer.Typer()
scrape_app = typer.Typer()
app.add_typer(scrape_app, name="scrape")


@scrape_app.command("profile")
def scrape_profile() -> None:
    """Stub unified profile scraping command."""
    raise NotImplementedError


@scrape_app.command("url")
def scrape_url() -> None:
    """Stub unified direct-URL scraping command."""
    raise NotImplementedError


def main() -> None:
    """Run the Typer application."""
    app()
