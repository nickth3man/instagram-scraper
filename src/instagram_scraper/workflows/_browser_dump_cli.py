# Copyright (c) 2026
"""CLI helpers for the browser_dump workflow."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

from instagram_scraper.workflows._browser_dump_fetch import _extract_shortcode
from instagram_scraper.workflows._browser_dump_types import (
    DEFAULT_DATA_DIR_FALLBACK,
    DEFAULT_USERNAME_FALLBACK,
    Config,
)


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool-dump-path", default=str(_default_tool_dump_path()))
    parser.add_argument("--output-dir", default=str(_default_output_dir()))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--max-comment-pages", type=int, default=100)
    parser.add_argument("--min-delay", type=float, default=0.05)
    parser.add_argument("--max-delay", type=float, default=0.2)
    parser.add_argument("--request-timeout", type=int, default=30)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--base-retry-seconds", type=float, default=2.0)
    parser.add_argument("--cookie-header", default=os.getenv("IG_COOKIE_HEADER", ""))
    args = parser.parse_args()
    return Config(
        tool_dump_path=Path(args.tool_dump_path),
        output_dir=Path(args.output_dir),
        should_resume=args.resume,
        should_reset_output=args.reset_output,
        start_index=max(0, args.start_index),
        limit=args.limit,
        checkpoint_every=max(1, args.checkpoint_every),
        max_comment_pages=max(1, args.max_comment_pages),
        min_delay=max(0.0, args.min_delay),
        max_delay=max(args.min_delay, args.max_delay),
        request_timeout=max(1, args.request_timeout),
        max_retries=max(1, args.max_retries),
        base_retry_seconds=max(0.1, args.base_retry_seconds),
        cookie_header=args.cookie_header,
    )


def _default_data_dir() -> Path:
    return Path(os.getenv("INSTAGRAM_DATA_DIR", DEFAULT_DATA_DIR_FALLBACK))


def _default_username() -> str:
    return os.getenv("INSTAGRAM_USERNAME", DEFAULT_USERNAME_FALLBACK)


def _default_tool_dump_path() -> Path:
    return _default_data_dir() / "tool_dump.json"


def _default_output_dir() -> Path:
    return _default_data_dir() / _default_username()


def _runtime_int(value: object, *, default: int) -> int:
    return value if isinstance(value, int) else default


def _runtime_float(value: object, *, default: float) -> float:
    return value if isinstance(value, int | float) else default


def _validate_instagram_post_urls(urls: list[str]) -> None:
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            message = "Instagram post URLs must use http or https"
            raise ValueError(message)
        if parsed.hostname not in {
            "instagram.com",
            "www.instagram.com",
            "m.instagram.com",
        }:
            message = "Instagram post URLs must target instagram.com"
            raise ValueError(message)
        if _extract_shortcode(url) is None:
            message = "Instagram post URLs must target a /p/ or /reel/ path"
            raise ValueError(message)
