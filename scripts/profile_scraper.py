#!/usr/bin/env python3
# Copyright (c) 2026
"""Profile Instagram scraper performance with Scalene.

This script helps identify performance bottlenecks in the Instagram scraper.
Run with: uv run scalene scripts/profile_scraper.py -- <scraper_args>

Examples:
    # Profile profile scraper
    uv run scalene --html --outfile=profile.html \
        scripts/profile_scraper.py -- profile --username cnn

    # Profile video downloader
    uv run scalene --html --outfile=profile.html \
        scripts/profile_scraper.py -- download --output-dir data/test

    # Profile browser dump scraper
    uv run scalene --html --outfile=profile.html \
        scripts/profile_scraper.py -- browser-dump \
        --tool-dump-path data/tool_dump.json

"""

from __future__ import annotations

import sys

from instagram_scraper.download_instagram_videos import (
    main as download_main,
)
from instagram_scraper.scrape_instagram_from_browser_dump import (
    main as browser_dump_main,
)
from instagram_scraper.scrape_instagram_profile import main as profile_main

MIN_ARGS = 2


def main() -> None:
    """Run profiler based on command-line arguments."""
    if len(sys.argv) < MIN_ARGS:
        sys.exit(1)

    scraper_type = sys.argv[1]
    scraper_args = sys.argv[2:]

    if scraper_type == "profile":
        sys.argv = ["scrape_instagram_profile", *scraper_args]
        profile_main()

    elif scraper_type == "download":
        sys.argv = ["download_instagram_videos", *scraper_args]
        download_main()

    elif scraper_type == "browser-dump":
        sys.argv = ["scrape_instagram_from_browser_dump", *scraper_args]
        browser_dump_main()

    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
