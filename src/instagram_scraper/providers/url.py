# Copyright (c) 2026
"""Provider for direct post URL scraping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from instagram_scraper.providers.base import build_run_summary, build_target_record
from instagram_scraper.scrape_instagram_from_browser_dump import run_url_scrape

if TYPE_CHECKING:
    from instagram_scraper.models import RunSummary, TargetRecord


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
        result = run_url_scrape(
            urls=[post_url],
            output_dir=destination,
            cookie_header=cookie_header,
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
    ) -> RunSummary:
        """Run the browser-dump flow for a list of URLs.

        Returns
        -------
        RunSummary
            A normalized summary describing the multi-URL scrape run.

        """
        urls = _load_urls(input_path)
        destination = output_dir or Path("data") / "urls"
        result = run_url_scrape(
            urls=urls,
            output_dir=destination,
            cookie_header=cookie_header,
            resume=resume,
            reset_output=reset_output,
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
    if isinstance(payload, dict):
        urls = payload.get("urls")
        if isinstance(urls, list):
            return [str(url) for url in urls]
    if isinstance(payload, list):
        return [str(url) for url in payload]
    return [line.strip() for line in text.splitlines() if line.strip()]


def _summary_int(
    payload: dict[str, object],
    key: str,
    *,
    fallback: int = 0,
) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) else fallback
