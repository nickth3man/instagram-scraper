from rich.console import Console
from rich.table import Table

from instagram_scraper.models import RunSummary


def render_run_summary(console: Console, summary: RunSummary) -> None:
    table = Table(title="Scrape Summary")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("mode", summary.mode)
    table.add_row("posts", str(summary.posts))
    table.add_row("comments", str(summary.comments))
    console.print(table)
