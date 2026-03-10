# Copyright (c) 2026
"""Extract Instagram posts using Playwright with an existing browser session."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import Page

FIELDNAMES = [
    "shortcode",
    "post_url",
    "media_id",
    "like_count",
    "comment_count",
    "caption",
    "is_video",
    "typename",
]


def _extract_post_data(page: Page, url: str) -> dict[str, Any]:
    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2500)
    html = page.content()
    data: dict[str, Any] = {
        "shortcode": url.split("/")[-2],
        "post_url": url,
        "media_id": None,
        "like_count": None,
        "comment_count": None,
        "caption": None,
        "is_video": None,
        "typename": None,
    }

    media_match = re.search(r'"media_id":"(\d+)_', html)
    if media_match is not None:
        data["media_id"] = media_match.group(1)

    desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)
    if desc_match is not None:
        desc = desc_match.group(1)
        like_match = re.search(r"(\d+(?:,\d+)*)\s+likes?", desc)
        if like_match is not None:
            data["like_count"] = int(like_match.group(1).replace(",", ""))
        comment_match = re.search(r"(\d+(?:,\d+)*)\s+comments?", desc)
        if comment_match is not None:
            data["comment_count"] = int(comment_match.group(1).replace(",", ""))
        if " - " in desc:
            data["caption"] = desc.split(" - ")[0]

    data["is_video"] = "video" in html.lower() and '"video_url"' in html
    data["typename"] = "GraphVideo" if data["is_video"] else "GraphImage"
    return data


def _main() -> int:
    data_dir = Path("data/believerofbuckets")
    input_file = data_dir / "tool_dump.json"
    output_file = data_dir / "posts.csv"

    with input_file.open(encoding="utf-8") as file:
        urls = json.load(file).get("urls", [])[:100]

    sys.stdout.write(f"Processing {len(urls)} posts with Playwright...\n")
    posts: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            ),
        )
        page = context.new_page()

        page.goto("https://www.instagram.com/", timeout=30000)
        page.wait_for_timeout(3000)

        for index, url in enumerate(urls, start=1):
            sys.stdout.write(f"[{index}/{len(urls)}] {url}... ")
            try:
                data = _extract_post_data(page, url)
                if data.get("media_id"):
                    posts.append(data)
                    sys.stdout.write(f"OK (media_id: {data['media_id']})\n")
                else:
                    errors.append({"url": url, "error": "no media_id"})
                    sys.stdout.write("FAIL (no media_id)\n")
            except (OSError, ValueError, TypeError) as error:
                errors.append({"url": url, "error": str(error)})
                sys.stdout.write(f"ERROR: {error}\n")

        browser.close()

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(posts)

    sys.stdout.write(f"\nComplete: {len(posts)} posts, {len(errors)} errors\n")
    sys.stdout.write(f"Output: {output_file}\n")
    return 0 if posts else 1


if __name__ == "__main__":
    raise SystemExit(_main())
