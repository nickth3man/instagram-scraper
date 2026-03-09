# Copyright (c) 2026
import importlib
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

async_http = importlib.import_module("instagram_scraper._async_http")


class _DummyContext:
    def __init__(self, resp):
        self.resp = resp

    async def __aenter__(self):
        return self.resp

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class _DummyClientSession:
    def __init__(self, connector=None, headers=None, raise_for_status=False):
        del raise_for_status
        self.connector = connector
        self.headers = headers or {}

    async def close(self):
        pass

    def get(self, url, params=None, timeout_seconds=None):
        pass


class _DummyResponse:
    def __init__(self, status, headers=None, payload=None):
        self.status = status
        self.headers = headers or {}
        self._payload = payload

    async def release(self):
        pass

    async def json(self):
        return self._payload


def test_build_async_instagram_session(monkeypatch) -> None:
    fake = types.ModuleType("aiohttp")
    fake.TCPConnector = MagicMock()
    fake.ClientSession = _DummyClientSession
    monkeypatch.setattr(async_http, "aiohttp", fake)
    monkeypatch.setattr(async_http, "AIOHTTP_AVAILABLE", True)

    cookie = "sessionid=123; csrftoken=abc"
    session = async_http.build_async_instagram_session(cookie)

    assert session.headers["Cookie"] == cookie
    assert session.headers["X-CSRFToken"] == "abc"


@pytest.mark.asyncio
async def test_async_request_with_retry_success() -> None:
    mock_response = _DummyResponse(200, payload={"ok": True})
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)

    retry_config = async_http.RetryConfig(
        timeout=5,
        max_retries=3,
        min_delay=0.1,
        max_delay=0.2,
        base_retry_seconds=0.1,
    )

    response, error = await async_http.async_request_with_retry(
        mock_session,
        "https://example.com",
        retry_config,
    )

    assert response == mock_response
    assert error is None
    assert mock_session.get.call_count == 1


@pytest.mark.asyncio
async def test_async_request_with_retry_retryable_failure() -> None:
    mock_response_fail = _DummyResponse(500)
    mock_response_success = _DummyResponse(200, payload={"ok": True})

    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        side_effect=[
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ],
    )

    retry_config = async_http.RetryConfig(
        timeout=5,
        max_retries=3,
        min_delay=0.01,
        max_delay=0.02,
        base_retry_seconds=0.01,
    )

    with patch("instagram_scraper._async_http.randomized_sleep", AsyncMock()):
        response, error = await async_http.async_request_with_retry(
            mock_session,
            "https://example.com",
            retry_config,
        )

    assert response == mock_response_success
    assert error is None
    assert mock_session.get.call_count == 3


@pytest.mark.asyncio
async def test_async_request_with_retry_exhausted() -> None:
    mock_response_fail = _DummyResponse(429)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response_fail)

    retry_config = async_http.RetryConfig(
        timeout=5,
        max_retries=2,
        min_delay=0.01,
        max_delay=0.02,
        base_retry_seconds=0.01,
    )

    with patch("instagram_scraper._async_http.randomized_sleep", AsyncMock()):
        response, error = await async_http.async_request_with_retry(
            mock_session,
            "https://example.com",
            retry_config,
        )

    assert response is None
    assert error == async_http.ErrorCode.REQUEST_FAILED
    assert mock_session.get.call_count == 2


@pytest.mark.asyncio
async def test_async_json_payload() -> None:
    mock_response = _DummyResponse(200, payload={"key": "value"})
    payload = await async_http.async_json_payload(mock_response)
    assert payload == {"key": "value"}
