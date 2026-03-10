# Copyright (c) 2026
"""Network and media parsing helpers for video_downloads."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from instagram_scraper.infrastructure.instagram_http import (
    RetryConfig,
    build_instagram_session,
    format_json_error,
    get_json_payload,
    randomized_delay,
    request_with_retry,
)
from instagram_scraper.workflows._video_download_types import (
    DEFAULT_BASE_RETRY_SECONDS,
    INITIAL_BEST_AREA,
    MEDIA_TYPE_CAROUSEL,
    MEDIA_TYPE_VIDEO,
    Config,
)

if TYPE_CHECKING:
    import requests


def _build_session(cookie_header: str) -> requests.Session:
    return build_instagram_session(cookie_header)


def _randomized_delay(cfg: Config, *, scale: float = 1.0) -> None:
    randomized_delay(cfg.min_delay, cfg.max_delay, scale=scale)


def _request_with_retry(
    session: requests.Session,
    url: str,
    cfg: Config,
    *,
    stream: bool,
) -> tuple[requests.Response | None, str | None]:
    return request_with_retry(
        session,
        url,
        RetryConfig(
            timeout=cfg.timeout,
            max_retries=cfg.max_retries,
            min_delay=cfg.min_delay,
            max_delay=cfg.max_delay,
            base_retry_seconds=DEFAULT_BASE_RETRY_SECONDS,
        ),
        stream=stream,
    )


def _fetch_media_info(
    session: requests.Session,
    media_id: str,
    cfg: Config,
) -> tuple[dict[str, object] | None, str | None]:
    response, error = _request_with_retry(
        session,
        f"https://www.instagram.com/api/v1/media/{media_id}/info/",
        cfg,
        stream=False,
    )
    if response is None:
        return None, error or "media_info_request_failed"
    payload = _json_payload(response)
    if payload is None:
        return None, _json_error(response, "media_info")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None, "media_info_empty"
    first = items[0]
    if not isinstance(first, dict):
        return None, "media_info_invalid"
    return cast("dict[str, object]", first), None


def _pick_best_video_url(video_versions: object) -> str | None:
    if not isinstance(video_versions, list):
        return None
    best_url: str | None = None
    best_area = INITIAL_BEST_AREA
    for version in video_versions:
        if not isinstance(version, dict):
            continue
        version_dict = cast("dict[str, object]", version)
        width = version_dict.get("width")
        height = version_dict.get("height")
        url = version_dict.get("url")
        if (
            not isinstance(width, int)
            or not isinstance(height, int)
            or not isinstance(url, str)
        ):
            continue
        area = width * height
        if area > best_area:
            best_area = area
            best_url = url
    return best_url


def _extract_video_entries(media_info: dict[str, object]) -> list[dict[str, object]]:
    media_type = media_info.get("media_type")
    if media_type == MEDIA_TYPE_VIDEO:
        video_url = _pick_best_video_url(media_info.get("video_versions"))
        return [] if video_url is None else [_video_entry(1, video_url)]
    if media_type != MEDIA_TYPE_CAROUSEL:
        return []
    entries: list[dict[str, object]] = []
    carousel_media = media_info.get("carousel_media")
    if not isinstance(carousel_media, list):
        return entries
    for index, child in enumerate(carousel_media, start=1):
        if not isinstance(child, dict):
            continue
        child_dict = cast("dict[str, object]", child)
        if child_dict.get("media_type") != MEDIA_TYPE_VIDEO:
            continue
        video_url = _pick_best_video_url(child_dict.get("video_versions"))
        if video_url is not None:
            entries.append(_video_entry(index, video_url))
    return entries


def _video_entry(position: int, video_url: str) -> dict[str, object]:
    return {
        "position": position,
        "media_type": MEDIA_TYPE_VIDEO,
        "video_url": video_url,
    }


def _json_payload(response: requests.Response) -> dict[str, object] | None:
    return get_json_payload(response)


def _json_error(response: requests.Response, prefix: str) -> str:
    return format_json_error(response, prefix)
