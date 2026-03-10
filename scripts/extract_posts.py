# Copyright (c) 2026
"""Extract Instagram post metadata using a cookie-authenticated HTTP session."""

from __future__ import annotations

import csv
import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

RetryConfig = importlib.import_module("instagram_scraper.config").RetryConfig
load_project_env = importlib.import_module(
    "instagram_scraper.infrastructure.env",
).load_project_env
_instagram_http = importlib.import_module(
    "instagram_scraper.infrastructure.instagram_http",
)
build_instagram_client = _instagram_http.build_instagram_client
request_with_retry = _instagram_http.request_with_retry

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


def _extract_post_data(
    session: requests.Session,
    shortcode: str,
) -> dict[str, Any] | None:
    url = f"https://www.instagram.com/p/{shortcode}/"
    retry = RetryConfig(
        timeout=20,
        max_retries=2,
        min_delay=1.0,
        max_delay=2.0,
        base_retry_seconds=1.0,
    )
    response, error = request_with_retry(session, url, retry)
    if response is None or error:
        return None

    html = response.text
    data: dict[str, Any] = {
        "shortcode": shortcode,
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

    if not input_file.exists():
        sys.stdout.write(f"Input file not found: {input_file}\n")
        return 1

    with input_file.open(encoding="utf-8") as file:
        data = json.load(file)

    urls = data.get("urls", [])[:100]
    shortcodes = [url.split("/")[-2] for url in urls if "/p/" in url or "/reel/" in url]
    sys.stdout.write(f"Processing {len(shortcodes)} posts...\n")

    load_project_env()
    cookie = os.getenv("IG_COOKIE_HEADER", "")
    if not cookie:
        sys.stdout.write("No IG_COOKIE_HEADER found in environment\n")
        return 1

    session = build_instagram_client(cookie)
    posts: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for index, shortcode in enumerate(shortcodes, start=1):
        sys.stdout.write(f"[{index}/{len(shortcodes)}] Processing {shortcode}... ")
        try:
            post_data = _extract_post_data(session, shortcode)
            if post_data is not None and post_data.get("media_id"):
                posts.append(post_data)
                message = (
                    f"OK (media_id: {post_data['media_id']}, "
                    f"likes: {post_data['like_count']})\n"
                )
                sys.stdout.write(message)
            else:
                errors.append({"shortcode": shortcode, "error": "No media_id found"})
                sys.stdout.write("FAIL (no media_id)\n")
        except (OSError, ValueError, TypeError) as error:
            errors.append({"shortcode": shortcode, "error": str(error)})
            sys.stdout.write(f"ERROR ({error})\n")

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(posts)

    sys.stdout.write(
        f"\nComplete: {len(posts)} posts extracted, {len(errors)} errors\n",
    )
    sys.stdout.write(f"Output: {output_file}\n")

    if errors:
        error_file = data_dir / "extraction_errors.json"
        with error_file.open("w", encoding="utf-8") as file:
            json.dump(errors, file, indent=2)
        sys.stdout.write(f"Errors saved to: {error_file}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
