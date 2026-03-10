# Copyright (c) 2026
"""Scrape Instagram post metadata and comments from a browser-tool URL dump."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from instagram_scraper.infrastructure.files import atomic_write_text, load_json_dict
from instagram_scraper.workflows._browser_dump_cli import (
    _runtime_float,
    _runtime_int,
    _validate_instagram_post_urls,
    parse_args,
)
from instagram_scraper.workflows._browser_dump_fetch import (
    _build_session,
    fetch_media_id,
)
from instagram_scraper.workflows._browser_dump_io import (
    _build_summary,
    _checkpoint_state,
    _ensure_output_csvs,
    _initial_metrics,
    _load_checkpoint,
    _output_headers,
    _prepare_output,
    _save_checkpoint,
)
from instagram_scraper.workflows._browser_dump_process import _process_url
from instagram_scraper.workflows._browser_dump_types import (
    Config,
    _RunContext,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


__all__ = ["Config", "fetch_media_id", "main", "parse_args", "run", "run_url_scrape"]


def run(cfg: Config) -> dict[str, object]:
    """Scrape every URL from the configured tool dump.

    Returns
    -------
        Summary dictionary describing the completed run.
    """
    urls = _load_urls_from_tool_dump(cfg.tool_dump_path)
    output_paths = _prepare_output(
        cfg.output_dir,
        should_reset_output=cfg.should_reset_output,
    )
    headers = _output_headers()
    _ensure_output_csvs(output_paths, headers, reset_output=cfg.should_reset_output)
    checkpoint = _load_checkpoint(cfg.output_dir) if cfg.should_resume else None
    metrics = _initial_metrics(cfg.start_index, cfg.limit, len(urls), checkpoint)
    session = _build_session(cfg.cookie_header)
    context = _RunContext(
        cfg=cfg,
        session=session,
        output_paths=output_paths,
        headers=headers,
        total_urls=len(urls),
        metrics=metrics,
    )
    try:
        for index in range(metrics["start_index"], metrics["end_index"]):
            _process_url(context, index, urls[index])
    finally:
        session.close()
    summary = _build_summary(cfg.output_dir, output_paths, metrics)
    atomic_write_text(cfg.output_dir / "summary.json", json.dumps(summary, indent=2))
    _save_checkpoint(
        cfg.output_dir, _checkpoint_state(metrics, len(urls), completed=True),
    )
    return summary


def run_url_scrape(
    *,
    urls: list[str],
    output_dir: Path,
    cookie_header: str,
    resume: bool = False,
    reset_output: bool = False,
    **runtime: object,
) -> dict[str, object]:
    """Run the workflow for an explicit list of Instagram post URLs.

    Returns
    -------
        Summary dictionary describing the completed run.
    """
    _validate_instagram_post_urls(urls)
    output_dir.mkdir(parents=True, exist_ok=True)
    tool_dump_path = output_dir / "tool_dump.json"
    tool_dump_path.write_text(
        json.dumps({"count": len(urls), "urls": urls}, indent=2),
        encoding="utf-8",
    )
    return run(
        Config(
            tool_dump_path=tool_dump_path,
            output_dir=output_dir,
            should_resume=resume,
            should_reset_output=reset_output,
            start_index=0,
            limit=None,
            checkpoint_every=_runtime_int(runtime.get("checkpoint_every"), default=20),
            max_comment_pages=100,
            min_delay=_runtime_float(runtime.get("min_delay"), default=0.05),
            max_delay=_runtime_float(runtime.get("max_delay"), default=0.2),
            request_timeout=_runtime_int(runtime.get("request_timeout"), default=30),
            max_retries=_runtime_int(runtime.get("max_retries"), default=5),
            base_retry_seconds=2.0,
            cookie_header=cookie_header,
        ),
    )


def main() -> None:
    """Run the browser-dump scraper and emit a JSON summary."""
    summary = run(parse_args())
    sys.stdout.write(json.dumps(summary) + "\n")


def _load_urls_from_tool_dump(path: Path) -> list[str]:
    payload = load_json_dict(path)
    if payload is not None:
        urls = payload.get("urls")
        if isinstance(urls, list):
            str_urls: list[str] = [item for item in urls if isinstance(item, str)]
            return str_urls
    text = path.read_text(encoding="utf-8")
    parsed_urls: list[str] = []
    for payload_item in _tool_dump_payloads(text):
        url = payload_item.get("url")
        if isinstance(url, str):
            parsed_urls.append(url)
    return parsed_urls


def _tool_dump_payloads(text: str) -> Generator[dict[str, object]]:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


if __name__ == "__main__":
    main()
