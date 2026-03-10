# Copyright (c) 2026
"""CLI helpers for the package entrypoint."""

from pathlib import Path
from typing import cast

import click
import typer

from instagram_scraper._cli_export_commands import register_export_commands
from instagram_scraper._cli_options import (
    REPORT_COMPARE_OPTION,
    REPORT_INPUT_ARGUMENT,
    REPORT_OUTPUT_OPTION,
    REPORT_TITLE_OPTION,
)
from instagram_scraper._cli_options import (
    STORIES_SEED_MESSAGE as _STORIES_SEED_MESSAGE,
)
from instagram_scraper._cli_scrape_commands import (
    register_scrape_commands,
    register_sync_commands,
)
from instagram_scraper.core.pipeline import run_pipeline
from instagram_scraper.infrastructure.env import load_project_env
from instagram_scraper.infrastructure.logging import LogContext, get_logger
from instagram_scraper.reporting.generator import (
    generate_comparison_report,
    generate_report,
)

STORIES_SEED_MESSAGE = _STORIES_SEED_MESSAGE

load_project_env()

app = typer.Typer(help="Unified one-shot Instagram scraping CLI.")
scrape_app = typer.Typer()
export_app = typer.Typer()
sync_app = typer.Typer()
report_app = typer.Typer()
logger = get_logger(__name__)

app.add_typer(scrape_app, name="scrape")
app.add_typer(export_app, name="export")
app.add_typer(sync_app, name="sync")
app.add_typer(report_app, name="report")


class InvalidComparisonDirectoriesError(typer.BadParameter):
    """Raised when one or more report comparison directories are invalid."""

    def __init__(self, invalid_dirs: list[Path]) -> None:
        invalid_list = ", ".join(str(path) for path in invalid_dirs)
        super().__init__(f"Invalid comparison directories: {invalid_list}")


def configure_scrape(
    ctx: typer.Context,
    *,
    raw_captures: bool | None = typer.Option(None, "--raw-captures/--no-raw-captures"),
    request_timeout: int = typer.Option(30, "--request-timeout"),
    max_retries: int = typer.Option(5, "--max-retries"),
    checkpoint_every: int = typer.Option(20, "--checkpoint-every"),
) -> None:
    """Capture shared runtime controls for scrape subcommands."""
    ctx.obj = {
        "raw_captures": raw_captures if raw_captures is not None else False,
        "request_timeout": request_timeout,
        "max_retries": max_retries,
        "checkpoint_every": checkpoint_every,
    }


def _current_context() -> typer.Context:
    return cast("typer.Context", click.get_current_context())


def _pipeline_kwargs(**kwargs: object) -> dict[str, object]:
    ctx = _current_context()
    shared = ctx.obj if isinstance(ctx.obj, dict) else {}
    return {**shared, **kwargs}


def _run(mode: str, **kwargs: object) -> None:
    raise typer.Exit(run_pipeline(mode, **_pipeline_kwargs(**kwargs)))


scrape_app.callback()(configure_scrape)
register_scrape_commands(scrape_app, run=_run)
register_sync_commands(sync_app, run=_run)
register_export_commands(export_app)


@report_app.callback()
def configure_report(
    ctx: typer.Context,
    *,
    output: Path = REPORT_OUTPUT_OPTION,
    title: str = REPORT_TITLE_OPTION,
    compare: str | None = REPORT_COMPARE_OPTION,
) -> None:
    """Capture shared report options for report subcommands."""
    ctx.obj = {"output": output, "title": title, "compare": compare}


@report_app.command("generate")
def report_generate(
    ctx: typer.Context,
    input_dir: Path = REPORT_INPUT_ARGUMENT,
) -> None:
    """Generate an interactive HTML analytics dashboard.

    Raises
    ------
    InvalidComparisonDirectoriesError
        If one or more comparison directories are invalid.
    """
    shared = ctx.obj if isinstance(ctx.obj, dict) else {}
    output = cast("Path", shared.get("output"))
    title = cast("str", shared.get("title", "Instagram Analytics Report"))
    compare = cast("str | None", shared.get("compare"))
    if compare:
        parts = [part.strip() for part in compare.split(",") if part.strip()]
        compare_dirs = [Path(part) for part in parts]
        invalid_dirs = [path for path in compare_dirs if not path.exists()]
        if invalid_dirs:
            raise InvalidComparisonDirectoriesError(invalid_dirs)
        result_path = generate_comparison_report(
            input_dir=input_dir,
            compare_dirs=compare_dirs,
            output_path=output,
            title=title,
        )
    else:
        result_path = generate_report(
            input_dir=input_dir,
            output_path=output,
            title=title,
        )
    with LogContext(output=str(result_path)):
        logger.info("report_generation_completed")
    typer.echo(f"Report generated: {result_path}")


def main() -> None:
    """Run the Typer application."""
    app()
