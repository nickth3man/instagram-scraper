# Copyright (c) 2026
"""Provider for direct post URL scraping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

from instagram_scraper.providers.base import build_run_summary, build_target_record
from instagram_scraper.workflows.browser_dump import run_url_scrape
from instagram_scraper.workflows.browser_html import run_browser_html_scrape

if TYPE_CHECKING:
    from instagram_scraper.models import RunSummary, TargetRecord


class _RuntimeKwargs(TypedDict, total=False):
    request_timeout: int
    max_retries: int
    checkpoint_every: int
    min_delay: float
    max_delay: float


class _BrowserRuntimeKwargs(TypedDict, total=False):
    browser_html: bool
    resume: bool
    reset_output: bool
    cookies_file: Path | None
    storage_state: Path | None
    user_data_dir: Path | None
    headed: bool
    timeout_ms: int


class UrlScrapeProvider:
    """Wrap direct-URL scraping in the unified provider interface."""

    @staticmethod
    def resolve_targets(
        *,
        post_url: str | None = None,
        input_path: Path | None = None,
    ) -> list[TargetRecord]:
        """Return normalized direct-URL targets.

        Returns
        -------
        list[TargetRecord]
            One target for a direct URL, or one per URL loaded from the input.

        """
        urls = [post_url] if post_url is not None else _load_urls(input_path)
        return [
            build_target_record(
                provider="http",
                target_kind="url",
                target_value=url,
                mode="urls" if input_path is not None else "url",
            )
            for url in urls
            if url is not None
        ]

    @staticmethod
    def run(
        *,
        post_url: str,
        output_dir: Path | None = None,
        cookie_header: str = "",
        **_: object,
    ) -> RunSummary:
        """Return a normalized summary for a direct-URL scrape.

        Returns
        -------
        RunSummary
            A normalized summary rooted under the URL shortcode when available.

        """
        shortcode = post_url.rstrip("/").split("/")[-1] or "url"
        destination = output_dir or Path("data") / shortcode
        result = _run_urls(
            urls=[post_url],
            output_dir=destination,
            cookie_header=cookie_header,
            runtime_kwargs=_,
        )
        return build_run_summary(
            "url",
            output_dir=destination,
            counts={
                "processed": _summary_int(result, "processed", fallback=1),
                "posts": _summary_int(result, "posts"),
                "comments": _summary_int(result, "comments"),
                "targets": 1,
                "errors": _summary_int(result, "errors"),
            },
        )

    @staticmethod
    def run_urls(
        *,
        input_path: Path,
        output_dir: Path | None = None,
        cookie_header: str = "",
        resume: bool = False,
        reset_output: bool = False,
        **_: object,
    ) -> RunSummary:
        """Run the browser-dump flow for a list of URLs.

        Returns
        -------
        RunSummary
            A normalized summary describing the multi-URL scrape run.

        """
        urls = _load_urls(input_path)
        destination = output_dir or Path("data") / "urls"
        result = _run_urls(
            urls=urls,
            output_dir=destination,
            cookie_header=cookie_header,
            runtime_kwargs={
                **_,
                "resume": resume,
                "reset_output": reset_output,
            },
        )
        return build_run_summary(
            "urls",
            output_dir=destination,
            counts={
                "processed": _summary_int(
                    result,
                    "processed",
                    fallback=len(urls),
                ),
                "posts": _summary_int(result, "posts"),
                "comments": _summary_int(result, "comments"),
                "targets": len(urls),
                "errors": _summary_int(result, "errors"),
            },
        )


def _load_urls(input_path: Path | None) -> list[str]:
    if input_path is None:
        return []
    text = input_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [line.strip() for line in text.splitlines() if line.strip()]
    urls = _urls_from_payload(payload)
    return [] if urls is None else urls


def _summary_int(
    payload: dict[str, object],
    key: str,
    *,
    fallback: int = 0,
) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) else fallback


def _urls_from_payload(payload: object) -> list[str] | None:
    if isinstance(payload, dict):
        urls = cast("dict[str, object]", payload).get("urls")
        return [str(url) for url in urls] if isinstance(urls, list) else []
    return [str(url) for url in payload] if isinstance(payload, list) else None


def _runtime_kwargs(kwargs: dict[str, object]) -> _RuntimeKwargs:
    runtime: _RuntimeKwargs = {}
    request_timeout = kwargs.get("request_timeout")
    max_retries = kwargs.get("max_retries")
    checkpoint_every = kwargs.get("checkpoint_every")
    min_delay = kwargs.get("min_delay")
    max_delay = kwargs.get("max_delay")
    if isinstance(request_timeout, int):
        runtime["request_timeout"] = request_timeout
    if isinstance(max_retries, int):
        runtime["max_retries"] = max_retries
    if isinstance(checkpoint_every, int):
        runtime["checkpoint_every"] = checkpoint_every
    if isinstance(min_delay, int | float):
        runtime["min_delay"] = float(min_delay)
    if isinstance(max_delay, int | float):
        runtime["max_delay"] = float(max_delay)
    return runtime


def _browser_runtime_kwargs(kwargs: dict[str, object]) -> _BrowserRuntimeKwargs:
    runtime: _BrowserRuntimeKwargs = {}
    browser_html = kwargs.get("browser_html")
    if isinstance(browser_html, bool):
        runtime["browser_html"] = browser_html
    for name in ("resume", "reset_output", "headed"):
        value = kwargs.get(name)
        if isinstance(value, bool):
            runtime[name] = value
    timeout_ms = kwargs.get("timeout_ms")
    if isinstance(timeout_ms, int):
        runtime["timeout_ms"] = timeout_ms
    for name in ("cookies_file", "storage_state", "user_data_dir"):
        value = kwargs.get(name)
        if isinstance(value, Path) or value is None:
            runtime[name] = value
    return runtime


def _run_urls(
    *,
    urls: list[str],
    output_dir: Path,
    cookie_header: str,
    runtime_kwargs: dict[str, object],
) -> dict[str, object]:
    browser_runtime = _browser_runtime_kwargs(runtime_kwargs)
    if browser_runtime.get("browser_html", False):
        return run_browser_html_scrape(
            urls=urls,
            output_dir=output_dir,
            **browser_runtime,
        )
    return run_url_scrape(
        urls=urls,
        output_dir=output_dir,
        cookie_header=cookie_header,
        **_runtime_kwargs(runtime_kwargs),
    )
