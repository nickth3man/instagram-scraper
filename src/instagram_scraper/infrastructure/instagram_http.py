# Copyright (c) 2026
"""Shared Instagram HTTP helpers."""

from __future__ import annotations

import os
import re
import time
from random import SystemRandom
from typing import cast

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import instagram_scraper.config as _config
from instagram_scraper.error_codes import (
    RETRYABLE_STATUS_CODES,
    ErrorCode,
    error_code_from_status,
)
from instagram_scraper.infrastructure.env import load_project_env

load_project_env()

RetryConfig = _config.RetryConfig

DEFAULT_USER_AGENT = os.getenv(
    "INSTAGRAM_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
)
SUCCESS_STATUS = 200
RETRYABLE_STATUSES = RETRYABLE_STATUS_CODES
SYSTEM_RANDOM = SystemRandom()
DEFAULT_POOL_CONNECTIONS = 10
DEFAULT_POOL_MAXSIZE = 10
DEFAULT_MAX_RETRIES = 3


def build_instagram_client(
    cookie_header: str,
    *,
    pool_connections: int = DEFAULT_POOL_CONNECTIONS,
    pool_maxsize: int = DEFAULT_POOL_MAXSIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> requests.Session:
    """Create a session with the headers Instagram endpoints expect.

    Returns
    -------
    requests.Session
        A configured session ready for Instagram requests.

    """
    session = requests.Session()

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=list(RETRYABLE_STATUSES),
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

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
    csrftoken = get_cookie_value(cookie_header, "csrftoken")
    session.headers.update(headers)
    if csrftoken:
        session.headers["X-CSRFToken"] = csrftoken
    return session


# Backward compatibility alias
build_instagram_session = build_instagram_client


def get_cookie_value(cookie_header: str, key: str) -> str | None:
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
    time.sleep(SYSTEM_RANDOM.uniform(min_delay * scale, max_delay * scale))


def request_with_retry(
    session: requests.Session,
    url: str,
    retry: RetryConfig,
    *,
    params: dict[str, str] | None = None,
    stream: bool = False,
) -> tuple[requests.Response | None, ErrorCode | None]:
    """Execute a GET request with retry and backoff for transient failures.

    Returns
    -------
    tuple[requests.Response | None, ErrorCode | None]
        The successful response, or an error code when retries are exhausted.

    """
    last_error: ErrorCode | None = None
    for attempt in range(1, retry.max_retries + 1):
        try:
            response = session.get(
                url,
                params=params,
                timeout=retry.timeout,
                stream=stream,
            )
        except requests.RequestException:
            last_error = ErrorCode.NETWORK_UNKNOWN
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
            last_error = error_code_from_status(response.status_code)
            randomized_delay(retry.min_delay, retry.max_delay, scale=wait_seconds)
            continue
        # Non-retryable status codes usually mean the request itself is wrong or
        # the caller lacks permission, so stop immediately.
        return None, error_code_from_status(response.status_code)
    return None, last_error or ErrorCode.REQUEST_FAILED


def get_json_payload(response: requests.Response) -> dict[str, object] | None:
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


def _sanitize_preview(text: str, max_length: int = 120) -> str:
    """Remove sensitive data from text before logging.

    Redacts cookies, tokens, and session identifiers.

    Returns
    -------
    str
        Sanitized text with sensitive values redacted.

    """
    sanitized = re.sub(
        r"(token|cookie|session|csrftoken|sessionid)=([^&\s;]+)",
        r"\1=REDACTED",
        text,
        flags=re.IGNORECASE,
    )
    return sanitized[:max_length].replace("\n", " ")


def format_json_error(response: requests.Response, prefix: str) -> str:
    """Summarize why a response body could not be treated as expected JSON.

    Returns
    -------
    str
        A stable error code that preserves response context for debugging.

    """
    content_type = (response.headers.get("content-type") or "").lower()
    preview = _sanitize_preview(response.text or "")
    if "json" not in content_type:
        return f"{prefix}_non_json:{content_type}:{preview}"
    return f"{prefix}_json_decode_failed"
