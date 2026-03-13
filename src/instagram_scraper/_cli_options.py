# Copyright (c) 2026
"""CLI option declarations shared across command modules."""

from pathlib import Path

import typer

DEFAULT_BROWSER_HTML = False
DEFAULT_BROWSER_HEADED = False

USERNAME_OPTION = typer.Option(..., "--username")
URL_OPTION = typer.Option(..., "--url", "--post-url")
HASHTAG_OPTION = typer.Option(..., "--hashtag")
LOCATION_OPTION = typer.Option(..., "--location")
INPUT_OPTION = typer.Option(..., "--input")
OUTPUT_DIR_OPTION = typer.Option(None, "--output-dir")
LIMIT_OPTION = typer.Option(None, "--limit")
POSTS_LIMIT_OPTION = typer.Option(None, "--posts-limit")
COOKIE_HEADER_OPTION = typer.Option(
    "",
    "--cookie-header",
    envvar="IG_COOKIE_HEADER",
    help=(
        "Instagram cookie header. Prefer IG_COOKIE_HEADER in your environment "
        "or .env file."
    ),
)
BROWSER_HTML_OPTION = typer.Option(
    DEFAULT_BROWSER_HTML,
    "--browser-html/--no-browser-html",
    help="Use Playwright-rendered browser HTML instead of the HTTP URL workflow.",
)
BROWSER_COOKIES_FILE_OPTION = typer.Option(
    None,
    "--cookies-file",
    help="Cookies JSON/JSONC file for browser HTML scraping.",
)
BROWSER_STORAGE_STATE_OPTION = typer.Option(
    None,
    "--storage-state",
    help="Playwright storage state file for browser HTML scraping.",
)
BROWSER_USER_DATA_DIR_OPTION = typer.Option(
    None,
    "--user-data-dir",
    help="Persistent Chromium profile directory for browser HTML scraping.",
)
BROWSER_HEADED_OPTION = typer.Option(
    DEFAULT_BROWSER_HEADED,
    "--headed/--headless",
    help="Run browser HTML scraping with a visible browser window.",
)
BROWSER_TIMEOUT_MS_OPTION = typer.Option(
    30000,
    "--timeout-ms",
    help="Browser HTML navigation timeout in milliseconds.",
)
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
EXPORT_OUTPUT_OPTION = typer.Option(..., "--output", "-o", help="Output file path")
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
