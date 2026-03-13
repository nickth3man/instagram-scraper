from pathlib import Path

import typer

from .scraper import scrape_profile

app = typer.Typer(help="Instagram Profile Scraper")


@app.command()
def scrape(
    username: str = typer.Argument(..., help="Instagram username (without @)"),
    limit: int = typer.Option(10, help="Number of most recent posts/reels to scrape"),
    output: Path = typer.Option(None, help="Custom output directory"),
):
    """Scrape recent posts/reels with media, comments, and likes."""
    scrape_profile(username, limit, output)


if __name__ == "__main__":
    app()
