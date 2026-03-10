from rich.console import Console

from instagram_scraper.models import RunSummary
from instagram_scraper.ui.presentation import render_run_summary


def test_render_run_summary_contains_mode_and_counts() -> None:
    console = Console(record=True)
    summary = RunSummary(
        run_id="run-1",
        mode="profile",
        processed=3,
        posts=2,
        comments=5,
        errors=0,
        output_dir="data/example",
    )
    render_run_summary(console, summary)
    output = console.export_text()
    assert "profile" in output
    assert "posts" in output.lower()
