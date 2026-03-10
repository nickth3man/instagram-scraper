# Copyright (c) 2026
"""CLI helpers for the package entrypoint."""

from datetime import datetime
from pathlib import Path
from typing import cast

import click
import typer

from instagram_scraper.core.pipeline import run_pipeline
from instagram_scraper.export_filters import ExportFilter, run_export
from instagram_scraper.infrastructure.logging import LogContext, get_logger
from instagram_scraper.infrastructure.structured_logging import (
    build_logger as build_structlog_logger,
)
from instagram_scraper.infrastructure.structured_logging import (
    configure_logging as configure_structlog_logging,
)
from instagram_scraper.reporting.generator import (
    generate_comparison_report,
    generate_report,
)

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
EXPORT_INPUT_ARGUMENT = typer.Argument(
    ...,
    exists=True,
    file_okay=False,
    dir_okay=True,
    readable=True,
    help="Directory containing NDJSON files from scraping",
)
EXPORT_FORMAT_OPTION = typer.Option(
    "csv",
    "--format",
    "-f",
    help="Output format: csv, excel, or parquet",
)
EXPORT_OUTPUT_OPTION = typer.Option(
    ...,
    "--output",
    "-o",
    help="Output file path",
)
EXPORT_TYPES_OPTION = typer.Option(
    None,
    "--types",
    "-t",
    help="Data types to export (comma-separated): posts,comments,users,stories",
)
EXPORT_SINCE_OPTION = typer.Option(
    None,
    "--since",
    help="Only include records after this date (ISO format: YYYY-MM-DD)",
)
EXPORT_UNTIL_OPTION = typer.Option(
    None,
    "--until",
    help="Only include records before this date (ISO format: YYYY-MM-DD)",
)
EXPORT_USERNAMES_OPTION = typer.Option(
    None,
    "--usernames",
    "-u",
    help="Filter by usernames (comma-separated)",
)
REPORT_INPUT_ARGUMENT = typer.Argument(
    ...,
    exists=True,
    file_okay=False,
    dir_okay=True,
    readable=True,
    help="Directory containing NDJSON files from scraping",
)
REPORT_OUTPUT_OPTION = typer.Option(
    Path("report.html"),
    "--output",
    "-o",
    help="Output HTML file path",
)
REPORT_TITLE_OPTION = typer.Option(
    "Instagram Analytics Report",
    "--title",
    "-t",
    help="Report title",
)
REPORT_COMPARE_OPTION = typer.Option(
    None,
    "--compare",
    "-c",
    help="Comma-separated list of additional profile directories to compare",
)


class InvalidComparisonDirectoriesError(typer.BadParameter):
    """Raised when one or more report comparison directories are invalid."""

    def __init__(self, invalid_dirs: list[Path]) -> None:
        """Initialize the error with the invalid comparison directories."""
        invalid_list = ", ".join(str(path) for path in invalid_dirs)
        super().__init__(f"Invalid comparison directories: {invalid_list}")


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


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        msg = f"Invalid date format: {value}. Use ISO format (YYYY-MM-DD)"
        raise typer.BadParameter(msg) from None


def _parse_types(value: str | None) -> frozenset[str] | None:
    if value is None:
        return None
    types_list = [t.strip().lower() for t in value.split(",") if t.strip()]
    if not types_list:
        return None
    valid_types = {"posts", "comments", "users", "stories"}
    for t in types_list:
        if t not in valid_types:
            valid_list = ", ".join(sorted(valid_types))
            msg = f"Invalid type: {t}. Valid types: {valid_list}"
            raise typer.BadParameter(msg) from None
    return frozenset(types_list)


def _parse_usernames(value: str | None) -> frozenset[str] | None:
    if value is None:
        return None
    usernames_list = [u.strip() for u in value.split(",") if u.strip()]
    return frozenset(usernames_list) if usernames_list else None


@export_app.callback()
def configure_export(
    ctx: typer.Context,
    *,
    format_name: str = EXPORT_FORMAT_OPTION,
    output: Path = EXPORT_OUTPUT_OPTION,
    types: str | None = EXPORT_TYPES_OPTION,
    since: str | None = EXPORT_SINCE_OPTION,
) -> None:
    """Capture shared export options for export subcommands."""
    ctx.obj = {
        "format_name": format_name,
        "output": output,
        "types": types,
        "since": since,
    }


@export_app.command("data")
def export_data(
    ctx: typer.Context,
    input_dir: Path = EXPORT_INPUT_ARGUMENT,
    until: str | None = EXPORT_UNTIL_OPTION,
    usernames: str | None = EXPORT_USERNAMES_OPTION,
) -> None:
    """Export scraped NDJSON data to another file format."""
    shared = ctx.obj if isinstance(ctx.obj, dict) else {}
    format_name = str(shared.get("format_name", "csv"))
    output = cast("Path", shared.get("output"))
    types = cast("str | None", shared.get("types"))
    since = cast("str | None", shared.get("since"))

    configure_structlog_logging()
    export_logger = build_structlog_logger(run_id="export", mode="export")

    export_filter = ExportFilter(
        types=_parse_types(types),
        usernames=_parse_usernames(usernames),
        since=_parse_date(since),
        until=_parse_date(until),
    )

    export_logger.info(
        "export_started",
        input_dir=str(input_dir),
        format=format_name,
        output=str(output),
    )

    result = run_export(
        input_dir=input_dir,
        output_path=output,
        format_name=format_name,
        export_filter=export_filter,
    )

    export_logger.info(
        "export_completed",
        rows_exported=result.rows_exported,
        files_processed=result.files_processed,
        types_exported=list(result.types_exported),
    )

    typer.echo(f"Exported {result.rows_exported} rows to {output}")
    if result.types_exported:
        typer.echo(f"Data types: {', '.join(sorted(result.types_exported))}")
    if result.files_processed:
        typer.echo(f"Files processed: {result.files_processed}")


@sync_app.command("profile")
def sync_profile(
    *,
    username: str = USERNAME_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
) -> None:
    """Run incremental sync for a profile."""
    _run("sync:profile", username=username, output_dir=output_dir)


@sync_app.command("hashtag")
def sync_hashtag(
    *,
    hashtag: str = HASHTAG_OPTION,
    limit: int | None = LIMIT_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run incremental sync for a hashtag."""
    _run(
        "sync:hashtag",
        hashtag=hashtag,
        limit=limit,
        output_dir=output_dir,
        cookie_header=cookie_header,
        has_auth=bool(cookie_header),
    )


@sync_app.command("location")
def sync_location(
    *,
    location: str = LOCATION_OPTION,
    limit: int | None = LIMIT_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
    cookie_header: str = COOKIE_HEADER_OPTION,
) -> None:
    """Run incremental sync for a location."""
    _run(
        "sync:location",
        location=location,
        limit=limit,
        output_dir=output_dir,
        cookie_header=cookie_header,
        has_auth=bool(cookie_header),
    )


@report_app.callback()
def configure_report(
    ctx: typer.Context,
    *,
    output: Path = REPORT_OUTPUT_OPTION,
    title: str = REPORT_TITLE_OPTION,
    compare: str | None = REPORT_COMPARE_OPTION,
) -> None:
    """Capture shared report options for report subcommands."""
    ctx.obj = {
        "output": output,
        "title": title,
        "compare": compare,
    }


@report_app.command("generate")
def report_generate(
    ctx: typer.Context,
    input_dir: Path = REPORT_INPUT_ARGUMENT,
) -> None:
    """Generate an interactive HTML analytics dashboard.

    Raises
    ------
    InvalidComparisonDirectoriesError
        Raised when any comparison directory does not exist.

    """
    shared = ctx.obj if isinstance(ctx.obj, dict) else {}
    output = cast("Path", shared.get("output"))
    title = cast("str", shared.get("title", "Instagram Analytics Report"))
    if compare := cast("str | None", shared.get("compare")):
        compare_dirs = [Path(p.strip()) for p in compare.split(",") if p.strip()]
        if invalid_dirs := [p for p in compare_dirs if not p.exists()]:
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
