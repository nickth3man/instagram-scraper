# Copyright (c) 2026
"""CLI helpers for the package entrypoint."""

import typer

app = typer.Typer()
scrape_app = typer.Typer()
app.add_typer(scrape_app, name="scrape")


@scrape_app.command("profile")
def scrape_profile() -> None:
    raise NotImplementedError


@scrape_app.command("url")
def scrape_url() -> None:
    raise NotImplementedError


def main() -> None:
    """Run the Typer application."""
    app()
