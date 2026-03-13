# Copyright (c) 2026
"""HTML parsing and cookie helpers for browser-backed URL scraping."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from instagram_scraper.workflows._browser_dump_types import _PostRow

Page = Any
INSTAGRAM_URL_PATTERN = re.compile(r"https://www\.instagram\.com/(?:p|reel)/[^/]+/?")
SHORTCODE_PATTERN = re.compile(r"/(?:p|reel)/([^/]+)/?$")
META_PATTERN_TEMPLATE = r'<meta[^>]+{attribute}="{name}"[^>]+content="([^"]*)"[^>]*>'


class _DescriptionCounts(TypedDict):
    like_count: int | None
    comment_count: int | None
    caption: str | None


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


def _extract_post_row_from_page(
    page: Page,
    url: str,
    *,
    timeout_ms: int,
) -> _PostRow:
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(1500)
    return _extract_post_row_from_html(page.content(), url)


def _extract_post_row_from_html(html: str, url: str) -> _PostRow:
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
    return (
        _first_match(
            html,
            [
                r'"is_video":true',
                r'<meta[^>]+property="og:video"',
                r'"product_type":"clips"',
            ],
        )
        is not None
    )


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
    return None if value is None else int(value.replace(",", ""))
