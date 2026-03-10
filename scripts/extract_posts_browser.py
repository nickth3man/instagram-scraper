# Copyright (c) 2026
"""Extract Instagram post metadata from authenticated browser HTML."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from html import unescape
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from collections.abc import Iterable

    from playwright.sync_api import Browser, BrowserContext, Page, Playwright

INSTAGRAM_URL_PATTERN = re.compile(r"https://www\.instagram\.com/(?:p|reel)/[^/]+/?")
SHORTCODE_PATTERN = re.compile(r"/(?:p|reel)/([^/]+)/")
META_PATTERN_TEMPLATE = r'<meta[^>]+{attribute}="{name}"[^>]+content="([^"]*)"[^>]*>'
POST_HEADER = [
    "media_id",
    "shortcode",
    "post_url",
    "type",
    "taken_at_utc",
    "caption",
    "like_count",
    "comment_count",
]
COMMENT_HEADER = [
    "media_id",
    "shortcode",
    "post_url",
    "id",
    "created_at_utc",
    "text",
    "comment_like_count",
    "owner_username",
    "owner_id",
]


class _DescriptionCounts(TypedDict):
    like_count: int | None
    comment_count: int | None
    caption: str | None


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
        help=(
            "Directory for posts.csv and comments.csv. "
            "Defaults to the input file directory."
        ),
    )
    parser.add_argument(
        "--cookies-file",
        type=Path,
        default=Path("currentcookies.jsonc"),
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
        help=(
            "Persistent Chromium profile directory with an existing "
            "authenticated session."
        ),
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chromium with a visible window.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30000,
        help="Navigation timeout in milliseconds.",
    )
    return parser.parse_args()


def _main() -> int:
    args = _parse_args()
    output_dir = args.output_dir or args.input_path.parent
    urls = _load_urls(args.input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_outputs(output_dir)

    if not urls:
        sys.stdout.write(f"No Instagram post URLs found in {args.input_path}\n")
        return 1

    posts_path = output_dir / "posts.csv"
    comments_path = output_dir / "comments.csv"
    sys.stdout.write(f"Processing {len(urls)} URLs from {args.input_path}\n")
    sys.stdout.write(f"Writing posts to {posts_path}\n")
    sys.stdout.write(f"Writing comments to {comments_path}\n")

    rows_written = 0
    browser: Browser | None = None
    with sync_playwright() as playwright:
        context, browser = _build_context(playwright, args)
        try:
            page = _context_page(context)
            for index, url in enumerate(urls, start=1):
                sys.stdout.write(f"[{index}/{len(urls)}] {url}\n")
                row = _extract_post_row_from_page(page, url, timeout_ms=args.timeout_ms)
                _append_csv_row(posts_path, POST_HEADER, row)
                rows_written += 1
        finally:
            context.close()
            if browser is not None:
                browser.close()

    sys.stdout.write(f"Extracted {rows_written} posts\n")
    return 0


def _load_urls(input_path: Path) -> list[str]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        message = f"Expected a JSON object in {input_path}"
        raise TypeError(message)
    raw_urls = payload.get("urls")
    if not isinstance(raw_urls, list):
        message = f"Expected 'urls' to be a list in {input_path}"
        raise TypeError(message)
    urls = [item for item in raw_urls if isinstance(item, str)]
    return [url for url in urls if INSTAGRAM_URL_PATTERN.fullmatch(url)]


def _ensure_outputs(output_dir: Path) -> None:
    _ensure_csv_with_header(output_dir / "posts.csv", POST_HEADER, reset=True)
    _ensure_csv_with_header(output_dir / "comments.csv", COMMENT_HEADER, reset=True)


def _build_context(
    playwright: Playwright,
    args: argparse.Namespace,
) -> tuple[BrowserContext, Browser | None]:
    if args.user_data_dir is not None:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(args.user_data_dir),
            headless=not args.headed,
            viewport={"width": 1440, "height": 1200},
        )
        return context, None

    browser = playwright.chromium.launch(headless=not args.headed)
    storage_state = str(args.storage_state) if args.storage_state is not None else None
    context = browser.new_context(
        storage_state=storage_state,
        viewport={"width": 1440, "height": 1200},
    )
    if args.cookies_file is not None and args.cookies_file.exists():
        cookies = _load_playwright_cookies(args.cookies_file)
        context.add_cookies(cast("Any", cookies))
    return context, browser


def _context_page(context: BrowserContext) -> Page:
    return context.pages[0] if context.pages else context.new_page()


def _ensure_csv_with_header(path: Path, header: list[str], *, reset: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset and path.exists():
        path.unlink()
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=header)
            writer.writeheader()


def _append_csv_row(path: Path, header: list[str], row: dict[str, object]) -> None:
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=header)
        writer.writerow(row)


def _load_playwright_cookies(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(_strip_jsonc_comments(path.read_text(encoding="utf-8")))
    if not isinstance(payload, list):
        message = f"Expected a cookie list in {path}"
        raise TypeError(message)
    cookies: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            cookie = _playwright_cookie(item)
            if cookie is not None:
                cookies.append(cookie)
    return cookies


def _strip_jsonc_comments(text: str) -> str:
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _playwright_cookie(payload: dict[str, object]) -> dict[str, Any] | None:
    name = payload.get("name")
    value = payload.get("value")
    domain = payload.get("domain")
    path = payload.get("path")
    secure = payload.get("secure")
    http_only = payload.get("httpOnly")
    same_site = payload.get("sameSite")
    expires = payload.get("expirationDate")
    if not all(isinstance(item, str) for item in (name, value, domain, path)):
        return None
    cookie: dict[str, Any] = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
        "secure": bool(secure),
        "httpOnly": bool(http_only),
    }
    if same_site in {"Lax", "None", "Strict"}:
        cookie["sameSite"] = same_site
    elif same_site == "lax":
        cookie["sameSite"] = "Lax"
    elif same_site == "strict":
        cookie["sameSite"] = "Strict"
    elif same_site in {"no_restriction", None}:
        cookie["sameSite"] = "None"
    if isinstance(expires, int | float):
        cookie["expires"] = float(expires)
    return cookie


def _extract_post_row_from_page(
    page: Page,
    url: str,
    *,
    timeout_ms: int,
) -> dict[str, object]:
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(1500)
    return _extract_post_row_from_html(page.content(), url)


def _extract_post_row_from_html(html: str, url: str) -> dict[str, object]:
    shortcode = _extract_shortcode(url)
    if shortcode is None:
        message = f"Unable to extract shortcode from {url}"
        raise ValueError(message)
    media_id = _first_match(
        html,
        [
            r'"media_id":"(\d+)"',
            r'<meta[^>]+property="al:ios:url"[^>]+content="instagram://media\?id=(\d+)"',
            rf'"shortcode":"{re.escape(shortcode)}".*?"id":"(\d+)"',
        ],
    )
    if media_id is None:
        message = f"Unable to extract media_id from {url}"
        raise ValueError(message)

    caption = _extract_caption(html)
    like_count = _extract_int(
        html,
        [
            r'"edge_media_preview_like":\{"count":(\d+)',
            r'"like_count":(\d+)',
            r'"likes":\{"count":(\d+)',
        ],
    )
    comment_count = _extract_int(
        html,
        [
            r'"edge_media_to_parent_comment":\{"count":(\d+)',
            r'"edge_media_to_comment":\{"count":(\d+)',
            r'"comment_count":(\d+)',
        ],
    )
    taken_at_utc = _extract_int(
        html,
        [
            r'"taken_at_timestamp":(\d+)',
            r'"taken_at":(\d+)',
            r'"taken_at_utc":(\d+)',
        ],
    )
    is_video = _extract_is_video(html)

    if like_count is None or comment_count is None or caption is None:
        description = _extract_meta_content(html, "property", "og:description")
        if description is None:
            description = _extract_meta_content(html, "name", "description")
        if description is not None:
            description_counts = _description_counts(description)
            if like_count is None:
                like_count = description_counts["like_count"]
            if comment_count is None:
                comment_count = description_counts["comment_count"]
            if caption is None:
                caption = description_counts["caption"]

    return {
        "media_id": media_id,
        "shortcode": shortcode,
        "post_url": url,
        "type": _media_type(html, is_video=is_video),
        "taken_at_utc": taken_at_utc,
        "caption": caption,
        "like_count": like_count,
        "comment_count": comment_count,
    }


def _extract_shortcode(url: str) -> str | None:
    match = SHORTCODE_PATTERN.search(url)
    return None if match is None else match.group(1)


def _extract_caption(html: str) -> str | None:
    caption = _first_match(
        html,
        [
            r'"edge_media_to_caption":\{"edges":\[\{"node":\{"text":"((?:\\.|[^"\\])*)"',
            r'"caption":\{"text":"((?:\\.|[^"\\])*)"',
        ],
        flags=re.DOTALL,
    )
    if caption is not None:
        return _decode_json_string(caption)
    description = _extract_meta_content(html, "property", "og:description")
    if description is None:
        description = _extract_meta_content(html, "name", "description")
    if description is None:
        return None
    return _description_counts(description)["caption"]


def _description_counts(description: str) -> _DescriptionCounts:
    text = unescape(description)
    like_match = re.search(r"([\d,]+)\s+likes?", text)
    comment_match = re.search(r"([\d,]+)\s+comments?", text)
    caption_match = re.search(r'-\s+[^:]+:\s+"([^\"]*)"', text)
    caption = caption_match.group(1) if caption_match is not None else None
    return {
        "like_count": _as_int(like_match.group(1)) if like_match is not None else None,
        "comment_count": (
            _as_int(comment_match.group(1)) if comment_match is not None else None
        ),
        "caption": caption,
    }


def _extract_meta_content(html: str, attribute: str, name: str) -> str | None:
    pattern = META_PATTERN_TEMPLATE.format(attribute=attribute, name=re.escape(name))
    match = re.search(pattern, html)
    return None if match is None else unescape(match.group(1))


def _extract_is_video(html: str) -> bool:
    return _first_match(
        html,
        [
            r'"is_video":true',
            r'<meta[^>]+property="og:video"',
            r'"product_type":"clips"',
        ],
    ) is not None


def _media_type(html: str, *, is_video: bool) -> int:
    sidecar_match = _first_match(
        html,
        [r'"__typename":"GraphSidecar"', r'"carousel_media":\['],
    )
    if sidecar_match is not None:
        return 8
    return 2 if is_video else 1


def _extract_int(html: str, patterns: Iterable[str]) -> int | None:
    value = _first_match(html, list(patterns), flags=re.DOTALL)
    return _as_int(value) if value is not None else None


def _first_match(
    html: str,
    patterns: list[str],
    *,
    flags: re.RegexFlag = re.NOFLAG,
) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, html, flags)
        if match is not None:
            return match.group(1) if match.groups() else match.group(0)
    return None


def _decode_json_string(value: str) -> str:
    return json.loads(f'"{value}"')


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    return int(value.replace(",", ""))


if __name__ == "__main__":
    raise SystemExit(_main())
