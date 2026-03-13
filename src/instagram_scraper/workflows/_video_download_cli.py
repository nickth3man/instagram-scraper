# Copyright (c) 2026
"""CLI helpers for video_downloads."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from instagram_scraper.workflows._video_download_types import (
    DEFAULT_DATA_DIR_FALLBACK,
    DEFAULT_USERNAME_FALLBACK,
    MIN_CHECKPOINT,
    MIN_CONCURRENT,
    MIN_DELAY_MINIMUM,
    MIN_RETRIES,
    MIN_TIMEOUT,
    Config,
)


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(_default_output_dir()))
    parser.add_argument("--posts-csv", default=None)
    parser.add_argument("--comments-csv", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    parser.add_argument("--min-delay", type=float, default=0.05)
    parser.add_argument("--max-delay", type=float, default=0.2)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cookie-header", default=os.getenv("IG_COOKIE_HEADER", ""))
    parser.add_argument("--max-concurrent-downloads", type=int, default=3)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    min_delay = max(MIN_DELAY_MINIMUM, args.min_delay)
    return Config(
        output_dir=output_dir,
        posts_csv=(
            Path(args.posts_csv)
            if args.posts_csv is not None
            else output_dir / "posts.csv"
        ),
        comments_csv=(
            Path(args.comments_csv)
            if args.comments_csv is not None
            else output_dir / "comments.csv"
        ),
        should_resume=args.resume,
        should_reset_output=args.reset_output,
        min_delay=min_delay,
        max_delay=max(min_delay, args.max_delay),
        max_retries=max(MIN_RETRIES, args.max_retries),
        timeout=max(MIN_TIMEOUT, args.timeout),
        checkpoint_every=max(MIN_CHECKPOINT, args.checkpoint_every),
        limit=args.limit,
        cookie_header=args.cookie_header,
        max_concurrent_downloads=max(MIN_CONCURRENT, args.max_concurrent_downloads),
    )


def _default_data_dir() -> Path:
    return Path(os.getenv("INSTAGRAM_DATA_DIR", DEFAULT_DATA_DIR_FALLBACK))


def _default_username() -> str:
    return os.getenv("INSTAGRAM_USERNAME", DEFAULT_USERNAME_FALLBACK)


def _default_output_dir() -> Path:
    return _default_data_dir() / _default_username()
