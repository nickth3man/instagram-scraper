# Copyright (c) 2026
"""Async Instagram HTTP helpers using aiohttp."""

from __future__ import annotations

import asyncio
import os
import re
from random import SystemRandom
from typing import TYPE_CHECKING, Any, Protocol, cast

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = cast("Any", None)
    AIOHTTP_AVAILABLE = False

from .config import RetryConfig
from .error_codes import ErrorCode, error_code_from_status

if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = [
    "RetryConfig",
    "async_json_payload",
    "async_request_with_retry",
    "build_async_instagram_session",
    "cookie_value",
    "randomized_sleep",
]


class _AsyncResponseLike(Protocol):
    status: int
    headers: Mapping[str, str]

    async def release(self) -> object: ...

    async def json(self) -> object: ...


class _AsyncSessionLike(Protocol):
    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        timeout_seconds: object,
    ) -> _AsyncResponseLike: ...


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
DEFAULT_POOL_LIMIT = 10
DEFAULT_POOL_LIMIT_PER_HOST = 10
DEFAULT_MAX_RETRIES = 3


def cookie_value(cookie_header: str, key: str) -> str | None:
    """Read a cookie value from a raw Cookie header string.

    Returns
    -------
    str | None
        The matching cookie value when present.

    """
    match = re.search(r"(?:^|; )" + re.escape(key) + r"=([^;]+)", cookie_header)
    return None if match is None else match.group(1)


def build_async_instagram_session(
    cookie_header: str,
    *,
    limit: int = DEFAULT_POOL_LIMIT,
    limit_per_host: int = DEFAULT_POOL_LIMIT_PER_HOST,
) -> object:
    """Create an async session with the headers Instagram endpoints expect.

    Returns
    -------
    aiohttp.ClientSession
        A configured session ready for Instagram requests.

    Raises
    ------
    ImportError
        If aiohttp is not installed.

    """
    if not AIOHTTP_AVAILABLE:
        msg = (
            "aiohttp is required for async HTTP operations. "
            "Install it with 'pip install aiohttp'."
        )
        raise ImportError(msg)

    connector = aiohttp.TCPConnector(limit=limit, limit_per_host=limit_per_host)

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
    if csrftoken:
        headers["X-CSRFToken"] = csrftoken

    return aiohttp.ClientSession(
        connector=connector,
        headers=headers,
        raise_for_status=False,
    )


async def randomized_sleep(
    min_delay: float,
    max_delay: float,
    *,
    scale: float = 1.0,
) -> None:
    """Sleep for a randomized delay within the configured bounds."""
    await asyncio.sleep(RANDOM.uniform(min_delay * scale, max_delay * scale))


async def async_request_with_retry(
    session: object,
    url: str,
    retry: RetryConfig,
    *,
    params: Mapping[str, str] | None = None,
) -> tuple[_AsyncResponseLike | None, ErrorCode | None]:
    """Execute a GET request with retry and backoff for transient failures.

    Returns
    -------
    tuple[aiohttp.ClientResponse | None, ErrorCode | None]
        The successful response, or an error code when retries are exhausted.

    """
    for attempt in range(1, retry.max_retries + 1):
        response, error = await _try_request(session, url, params, retry, attempt)
        if error is None:
            return response, None
        if not _is_retryable_error(error):
            return None, error

    return None, ErrorCode.REQUEST_FAILED


async def _try_request(
    session: object,
    url: str,
    params: Mapping[str, str] | None,
    retry: RetryConfig,
    attempt: int,
) -> tuple[_AsyncResponseLike | None, ErrorCode | None]:
    """Attempt a single HTTP request with error handling.

    Returns
    -------
    tuple[aiohttp.ClientResponse | None, ErrorCode | None]
        The response if successful, or an error code.

    """
    try:
        response = await cast("_AsyncSessionLike", session).get(
            url,
            params=params,
            timeout_seconds=aiohttp.ClientTimeout(total=retry.timeout),
        )
        return await _handle_response(response, retry, attempt)
    except TimeoutError:
        await randomized_sleep(
            retry.min_delay,
            retry.max_delay,
            scale=retry.base_retry_seconds * (2 ** (attempt - 1)),
        )
        return None, ErrorCode.NETWORK_TIMEOUT
    except aiohttp.ClientError:
        await randomized_sleep(
            retry.min_delay,
            retry.max_delay,
            scale=retry.base_retry_seconds * (2 ** (attempt - 1)),
        )
        return None, ErrorCode.NETWORK_CONNECTION


async def _handle_response(
    response: _AsyncResponseLike,
    retry: RetryConfig,
    attempt: int,
) -> tuple[_AsyncResponseLike | None, ErrorCode | None]:
    """Handle HTTP response, releasing resources and determining retry strategy.

    Returns
    -------
    tuple[aiohttp.ClientResponse | None, ErrorCode | None]
        The response if successful, or an error code for retry/non-retry cases.

    """
    if response.status == SUCCESS_STATUS:
        return response, None

    if response.status in RETRYABLE_STATUSES:
        wait_seconds = _calculate_retry_wait(response, retry, attempt)
        error = error_code_from_status(response.status)
        await response.release()
        await randomized_sleep(
            retry.min_delay,
            retry.max_delay,
            scale=wait_seconds,
        )
        return None, error

    await response.release()
    return None, error_code_from_status(response.status)


def _calculate_retry_wait(
    response: _AsyncResponseLike,
    retry: RetryConfig,
    attempt: int,
) -> float:
    """Calculate wait time for retry based on Retry-After header or exponential backoff.

    Returns
    -------
    float
        Seconds to wait before retrying.

    """
    retry_after = response.headers.get("Retry-After")
    if retry_after and retry_after.replace(".", "", 1).isdigit():
        return float(retry_after)
    return retry.base_retry_seconds * (2 ** (attempt - 1))


def _is_retryable_error(error: ErrorCode | None) -> bool:
    """Determine if an error code indicates a retryable condition.

    Returns
    -------
    bool
        True if the error should trigger a retry.

    """
    if error is None:
        return False
    retryable_codes = {
        ErrorCode.HTTP_429,
        ErrorCode.HTTP_500,
        ErrorCode.HTTP_502,
        ErrorCode.HTTP_503,
        ErrorCode.HTTP_504,
        ErrorCode.NETWORK_TIMEOUT,
        ErrorCode.NETWORK_CONNECTION,
    }
    return error in retryable_codes


async def async_json_payload(
    response: _AsyncResponseLike,
) -> dict[str, object] | None:
    """Decode a JSON object response body.

    Returns
    -------
    dict[str, object] | None
        The decoded payload when the response body is a JSON object.

    """
    try:
        payload = await cast("Any", response).json()
    except (aiohttp.ContentTypeError, ValueError):
        return None

    return cast("dict[str, object]", payload) if isinstance(payload, dict) else None
