# Copyright (c) 2026
"""Browser-backed URL scraping using Playwright-rendered Instagram HTML."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

from instagram_scraper.error_codes import ErrorCode
from instagram_scraper.exceptions import InstagramError
from instagram_scraper.infrastructure.files import atomic_write_text
from instagram_scraper.workflows._browser_dump_cli import _validate_instagram_post_urls
from instagram_scraper.workflows._browser_dump_io import (
    _build_summary,
    _checkpoint_next_index,
    _checkpoint_state,
    _ensure_output_csvs,
    _increment_metric,
    _initial_metrics,
    _load_checkpoint,
    _output_headers,
    _prepare_output,
    _record_processing_error,
    _save_checkpoint,
    _write_post_artifact,
)
from instagram_scraper.workflows._browser_html_extraction import (
    INSTAGRAM_URL_PATTERN,
    _extract_post_row_from_html,
    _extract_post_row_from_page,
    _extract_shortcode,
    _load_playwright_cookies,
)
from instagram_scraper.workflows._workflow_inputs import load_tool_dump_urls

if TYPE_CHECKING:
    from instagram_scraper.workflows._browser_dump_types import (
        _OutputPaths,
        _PostRow,
        _RunMetrics,
    )

try:
    _playwright_sync = importlib.import_module("playwright.sync_api")
except ImportError:
    _playwright_sync = None

sync_playwright = None if _playwright_sync is None else _playwright_sync.sync_playwright
Browser = BrowserContext = Page = Playwright = Any
PlaywrightError = RuntimeError if _playwright_sync is None else _playwright_sync.Error

_DEFAULT_COOKIES_FILE = Path("currentcookies.jsonc")
_DEFAULT_TIMEOUT_MS = 30000
_DEFAULT_CHECKPOINT_EVERY = 20
_DEFAULT_VIEWPORT = {"width": 1440, "height": 1200}


class _BrowserRunKwargs(TypedDict, total=False):
    resume: bool
    reset_output: bool
    start_index: int
    limit: int | None
    checkpoint_every: int
    cookies_file: Path | None
    storage_state: Path | None
    user_data_dir: Path | None
    headed: bool
    timeout_ms: int


@dataclass(frozen=True, slots=True)
class _ProcessContext:
    output_paths: _OutputPaths
    headers: dict[str, list[str]]
    metrics: _RunMetrics
    timeout_ms: int


__all__ = [
    "extract_post_row_from_html",
    "load_playwright_cookies",
    "main",
    "run_browser_html_scrape",
]


def run_browser_html_scrape(
    *,
    urls: list[str],
    output_dir: Path,
    **runtime: object,
) -> dict[str, object]:
    """Scrape explicit Instagram post URLs from browser-rendered HTML.

    Returns
    -------
        Summary dictionary describing the completed run.

    Raises
    ------
    InstagramError
        If Playwright is not installed.
    """
    _validate_instagram_post_urls(urls)
    if sync_playwright is None:
        message = "Playwright is required for browser HTML scraping"
        raise InstagramError(message, code=ErrorCode.INVALID_ARTIFACT)

    resolved = _runtime_kwargs(runtime)
    output_paths = _prepare_output(
        output_dir,
        should_reset_output=resolved.get("reset_output", False),
    )
    headers = _output_headers()
    _ensure_output_csvs(
        output_paths,
        headers,
        reset_output=resolved.get("reset_output", False),
    )
    checkpoint = (
        _load_checkpoint(output_dir) if resolved.get("resume", False) else None
    )
    metrics = _initial_metrics(
        resolved.get("start_index", 0),
        resolved.get("limit"),
        len(urls),
        checkpoint,
    )
    checkpoint_every = max(
        resolved.get("checkpoint_every", _DEFAULT_CHECKPOINT_EVERY),
        1,
    )
    process_context = _ProcessContext(
        output_paths=output_paths,
        headers=headers,
        metrics=metrics,
        timeout_ms=resolved.get("timeout_ms", _DEFAULT_TIMEOUT_MS),
    )

    with sync_playwright() as playwright:
        context, browser = _build_context(playwright, resolved)
        try:
            page = _context_page(context)
            for index in range(metrics["start_index"], metrics["end_index"]):
                _process_url(process_context, page, urls[index], index)
                if metrics["processed"] % checkpoint_every == 0:
                    _checkpoint_next_index(output_dir, metrics, len(urls), index)
        finally:
            context.close()
            if browser is not None:
                browser.close()

    summary = _build_summary(output_dir, output_paths, metrics)
    atomic_write_text(output_dir / "summary.json", json.dumps(summary, indent=2))
    _save_checkpoint(
        output_dir,
        _checkpoint_state(metrics, len(urls), completed=True),
    )
    return summary


def main() -> int:
    """Run the browser-backed URL scraper and emit a JSON summary.

    Returns
    -------
        Process exit code.
    """
    args = _parse_args()
    output_dir = args.output_dir or args.input_path.parent
    urls = _load_urls(args.input_path)
    if not urls:
        sys.stdout.write(f"No Instagram post URLs found in {args.input_path}\n")
        return 1
    summary = run_browser_html_scrape(
        urls=urls,
        output_dir=output_dir,
        resume=args.resume,
        reset_output=args.reset_output,
        start_index=args.start_index,
        limit=args.limit,
        checkpoint_every=args.checkpoint_every,
        cookies_file=args.cookies_file,
        storage_state=args.storage_state,
        user_data_dir=args.user_data_dir,
        headed=args.headed,
        timeout_ms=args.timeout_ms,
    )
    sys.stdout.write(json.dumps(summary) + "\n")
    return 0


def extract_post_row_from_html(html: str, url: str) -> _PostRow:
    """Return one normalized post row extracted from page HTML.

    Returns
    -------
        Normalized post row extracted from browser-rendered HTML.
    """
    return _extract_post_row_from_html(html, url)


def load_playwright_cookies(path: Path) -> list[dict[str, Any]]:
    """Return Playwright cookies loaded from a JSON or JSONC export.

    Returns
    -------
        Cookie payload ready for ``BrowserContext.add_cookies``.
    """
    return _load_playwright_cookies(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Instagram post metadata from page HTML via Playwright.",
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="JSON file containing {'urls': [...]}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for artifacts. Defaults to the input file directory.",
    )
    parser.add_argument(
        "--cookies-file",
        type=Path,
        default=_DEFAULT_COOKIES_FILE,
        help="JSON or JSONC cookies export used to seed a logged-in context.",
    )
    parser.add_argument(
        "--storage-state",
        type=Path,
        default=None,
        help="Playwright storage state file for an authenticated session.",
    )
    parser.add_argument(
        "--user-data-dir",
        type=Path,
        default=None,
        help="Persistent Chromium profile directory with an authenticated session.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the last checkpoint when checkpoint.json exists.",
    )
    parser.add_argument(
        "--reset-output",
        action="store_true",
        help="Delete previous output artifacts before starting.",
    )
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=_DEFAULT_CHECKPOINT_EVERY,
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chromium with a visible window.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=_DEFAULT_TIMEOUT_MS,
        help="Navigation timeout in milliseconds.",
    )
    return parser.parse_args()


def _runtime_int(value: object, *, minimum: int = 0) -> int | None:
    return max(value, minimum) if isinstance(value, int) else None


def _runtime_path(value: object) -> Path | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return Path(value)
    if isinstance(value, Path) and value != Path():
        return value
    return None


def _runtime_kwargs(kwargs: dict[str, object]) -> _BrowserRunKwargs:
    runtime: _BrowserRunKwargs = {}
    for name in ("resume", "reset_output", "headed"):
        value = kwargs.get(name)
        if isinstance(value, bool):
            runtime[name] = value
    start_index = _runtime_int(kwargs.get("start_index"), minimum=0)
    if start_index is not None:
        runtime["start_index"] = start_index
    checkpoint_every = _runtime_int(kwargs.get("checkpoint_every"), minimum=1)
    if checkpoint_every is not None:
        runtime["checkpoint_every"] = checkpoint_every
    timeout_ms = _runtime_int(kwargs.get("timeout_ms"), minimum=1)
    if timeout_ms is not None:
        runtime["timeout_ms"] = timeout_ms
    limit = kwargs.get("limit")
    if isinstance(limit, int):
        runtime["limit"] = max(limit, 0)
    elif limit is None:
        runtime["limit"] = None
    for name in ("cookies_file", "storage_state", "user_data_dir"):
        runtime[name] = _runtime_path(kwargs.get(name))
    return runtime


def _load_urls(input_path: Path) -> list[str]:
    return load_tool_dump_urls(
        input_path,
        validator=lambda url: INSTAGRAM_URL_PATTERN.fullmatch(url) is not None,
    )


def _build_context(
    playwright: Playwright,
    runtime: _BrowserRunKwargs,
) -> tuple[BrowserContext, Browser | None]:
    user_data_dir = runtime.get("user_data_dir")
    headed = runtime.get("headed", False)
    if user_data_dir is not None:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=not headed,
            viewport=_DEFAULT_VIEWPORT,
        )
        return context, None

    browser = playwright.chromium.launch(headless=not headed)
    storage_state = runtime.get("storage_state")
    context = browser.new_context(
        storage_state=(str(storage_state) if storage_state is not None else None),
        viewport=_DEFAULT_VIEWPORT,
    )
    cookies_file = runtime.get("cookies_file")
    if cookies_file is not None and cookies_file.exists():
        context.add_cookies(cast("Any", _load_playwright_cookies(cookies_file)))
    return context, browser


def _context_page(context: BrowserContext) -> Page:
    return context.pages[0] if context.pages else context.new_page()


def _process_url(
    context: _ProcessContext,
    page: Page,
    url: str,
    index: int,
) -> None:
    try:
        row = _extract_post_row_from_page(page, url, timeout_ms=context.timeout_ms)
    except (PlaywrightError, ValueError) as exc:
        _record_processing_error(
            context.output_paths,
            context.headers["errors"],
            context.metrics,
            {
                "index": index,
                "post_url": url,
                "shortcode": _extract_shortcode(url),
                "media_id": None,
                "stage": "extract_post_from_html",
                "error": type(exc).__name__,
            },
        )
    else:
        _write_post_artifact(
            context.output_paths,
            context.headers["posts"],
            context.metrics,
            row,
        )
    _increment_metric(context.metrics, "processed")


if __name__ == "__main__":
    raise SystemExit(main())
