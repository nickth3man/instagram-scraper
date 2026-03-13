# Copyright (c) 2026

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from instagram_scraper.error_codes import ErrorCode
from instagram_scraper.exceptions import InstagramError
from instagram_scraper.infrastructure.files import load_json_dict

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def load_tool_dump_urls(
    input_path: Path,
    *,
    limit: int | None = None,
    validator: Callable[[str], bool] | None = None,
) -> list[str]:
    try:
        payload = load_json_dict(input_path)
    except OSError as exc:
        message = f"Unable to read tool dump from {input_path}"
        raise InstagramError(message, code=ErrorCode.FILE_READ_ERROR) from exc
    if payload is None:
        try:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
        except OSError as exc:
            message = f"Unable to read tool dump from {input_path}"
            raise InstagramError(message, code=ErrorCode.FILE_READ_ERROR) from exc
        except json.JSONDecodeError as exc:
            message = f"Expected valid JSON in {input_path}"
            raise InstagramError(message, code=ErrorCode.PARSE_JSON_DECODE) from exc
    if not isinstance(payload, dict):
        message = f"Expected a JSON object in {input_path}"
        raise InstagramError(message, code=ErrorCode.PARSE_INVALID_SHAPE)
    raw_urls = payload.get("urls")
    if not isinstance(raw_urls, list):
        message = f"Expected 'urls' to be a list in {input_path}"
        raise InstagramError(message, code=ErrorCode.PARSE_INVALID_SHAPE)
    if any(not isinstance(item, str) for item in raw_urls):
        message = f"Expected only string URLs in {input_path}"
        raise InstagramError(message, code=ErrorCode.PARSE_INVALID_SHAPE)
    urls = cast("list[str]", list(raw_urls))
    if limit is not None:
        urls = urls[: max(limit, 0)]
    if validator is None:
        return urls
    return [url for url in urls if validator(url)]
