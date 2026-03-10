# Copyright (c) 2026
"""Rich terminal rendering helpers."""

from rich.console import Console
from rich.table import Table

from instagram_scraper.models import RunSummary, SyncSummary


def render_run_summary(console: Console, summary: RunSummary) -> None:
    """Render a compact run summary table to the terminal."""
    table = Table(title="Scrape Summary")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("mode", summary.mode)
    table.add_row("support", summary.support_tier)
    table.add_row("targets", str(summary.targets))
    table.add_row("posts", str(summary.posts))
    table.add_row("comments", str(summary.comments))
    table.add_row("stories", str(summary.stories))
    console.print(table)


def render_sync_summary(console: Console, summary: SyncSummary) -> None:
    """Render a compact sync summary table to the terminal."""
    table = Table(title="Sync Summary")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("mode", summary.mode)
    table.add_row("target", summary.target_key)
    table.add_row("first_sync", "yes" if summary.first_sync else "no")
    table.add_row("new_posts", str(summary.new_posts))
    table.add_row("skipped_posts", str(summary.skipped_posts))
    table.add_row("total_posts", str(summary.total_posts))
    table.add_row("errors", str(summary.errors))
    console.print(table)
