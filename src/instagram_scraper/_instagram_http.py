# Copyright (c) 2026
"""Shared Instagram HTTP helpers."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from random import SystemRandom
from typing import cast

import requests

DEFAULT_USER_AGENT = os.getenv(
    "INSTAGRAM_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
)
SUCCESS_STATUS = 200
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
RANDOM = SystemRandom()


@dataclass(frozen=True)
class RetryConfig:
    """HTTP retry settings shared across Instagram API callers."""

    timeout: int
    max_retries: int
    min_delay: float
    max_delay: float
    base_retry_seconds: float


def build_instagram_session(cookie_header: str) -> requests.Session:
    """Create a session with the headers Instagram endpoints expect.

    Returns
    -------
    requests.Session
        A configured session ready for Instagram requests.

    """
    session = requests.Session()
    # These headers make our requests look like a normal browser session instead
    # of a completely generic script.
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.instagram.com/",
        "Cookie": cookie_header,
    }
    app_id = os.getenv("INSTAGRAM_APP_ID")
    asbd_id = os.getenv("INSTAGRAM_ASBD_ID")
    if app_id:
        headers["X-IG-App-ID"] = app_id
    if asbd_id:
        headers["X-ASBD-ID"] = asbd_id
    csrftoken = cookie_value(cookie_header, "csrftoken")
    session.headers.update(headers)
    if csrftoken:
        # Some Instagram endpoints expect the CSRF token as both a cookie and a
        # header, so copy it over when the cookie is present.
        session.headers["X-CSRFToken"] = csrftoken
    return session


def cookie_value(cookie_header: str, key: str) -> str | None:
    """Read a cookie value from a raw Cookie header string.

    Returns
    -------
    str | None
        The matching cookie value when present.

    """
    match = re.search(r"(?:^|; )" + re.escape(key) + r"=([^;]+)", cookie_header)
    return None if match is None else match.group(1)


def randomized_delay(
    min_delay: float,
    max_delay: float,
    *,
    scale: float = 1.0,
) -> None:
    """Sleep for a randomized delay within the configured bounds."""
    time.sleep(RANDOM.uniform(min_delay * scale, max_delay * scale))


def request_with_retry(
    session: requests.Session,
    url: str,
    retry: RetryConfig,
    *,
    params: dict[str, str] | None = None,
    stream: bool = False,
) -> tuple[requests.Response | None, str | None]:
    """Execute a GET request with retry and backoff for transient failures.

    Returns
    -------
    tuple[requests.Response | None, str | None]
        The successful response, or an error code when retries are exhausted.

    """
    last_error: str | None = None
    for attempt in range(1, retry.max_retries + 1):
        try:
            response = session.get(
                url,
                params=params,
                timeout=retry.timeout,
                stream=stream,
            )
        except requests.RequestException as exc:
            last_error = f"request_exception:{exc.__class__.__name__}"
            randomized_delay(
                retry.min_delay,
                retry.max_delay,
                scale=retry.base_retry_seconds * (2 ** (attempt - 1)),
            )
            continue
        if response.status_code == SUCCESS_STATUS:
            return response, None
        if response.status_code in RETRYABLE_STATUSES:
            # Rate limits and temporary server failures are often solved by
            # waiting longer and trying again.
            retry_after = response.headers.get("Retry-After")
            wait_seconds = (
                float(retry_after)
                if retry_after and retry_after.isdigit()
                else retry.base_retry_seconds * (2 ** (attempt - 1))
            )
            last_error = f"http_{response.status_code}"
            randomized_delay(retry.min_delay, retry.max_delay, scale=wait_seconds)
            continue
        # Non-retryable status codes usually mean the request itself is wrong or
        # the caller lacks permission, so stop immediately.
        return None, f"http_{response.status_code}"
    return None, last_error or "request_failed"


def json_payload(response: requests.Response) -> dict[str, object] | None:
    """Decode a JSON object response body.

    Returns
    -------
    dict[str, object] | None
        The decoded payload when the response body is a JSON object.

    """
    try:
        payload = response.json()
    except ValueError:
        return None
    # Callers expect a JSON object with named fields. Lists or simple values are
    # treated as an unexpected shape.
    return cast("dict[str, object]", payload) if isinstance(payload, dict) else None


def json_error(response: requests.Response, prefix: str) -> str:
    """Summarize why a response body could not be treated as expected JSON.

    Returns
    -------
    str
        A stable error code that preserves response context for debugging.

    """
    content_type = (response.headers.get("content-type") or "").lower()
    preview = (response.text or "")[:120].replace("\n", " ")
    if "json" not in content_type:
        return f"{prefix}_non_json:{content_type}:{preview}"
    return f"{prefix}_json_decode_failed"
