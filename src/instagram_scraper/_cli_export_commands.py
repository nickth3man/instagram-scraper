# Copyright (c) 2026
"""Export command registrations for the Typer CLI."""

from datetime import datetime
from pathlib import Path
from typing import cast

import typer

from instagram_scraper._cli_options import (
    EXPORT_FORMAT_OPTION,
    EXPORT_INPUT_ARGUMENT,
    EXPORT_OUTPUT_OPTION,
    EXPORT_SINCE_OPTION,
    EXPORT_TYPES_OPTION,
    EXPORT_UNTIL_OPTION,
    EXPORT_USERNAMES_OPTION,
)
from instagram_scraper.export_filters import ExportFilter, run_export
from instagram_scraper.infrastructure.structured_logging import (
    build_logger as build_structlog_logger,
)
from instagram_scraper.infrastructure.structured_logging import (
    configure_logging as configure_structlog_logging,
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


def register_export_commands(export_app: typer.Typer) -> None:
    """Register `export` subcommands on the provided app."""

    @export_app.callback()
    def configure_export(
        ctx: typer.Context,
        *,
        format_name: str = EXPORT_FORMAT_OPTION,
        output: Path = EXPORT_OUTPUT_OPTION,
        types: str | None = EXPORT_TYPES_OPTION,
        since: str | None = EXPORT_SINCE_OPTION,
    ) -> None:
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
