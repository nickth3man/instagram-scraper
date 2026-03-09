import pytest

from instagram_scraper.exceptions import (
    AuthenticationError,
    InstagramAPIError,
    InstagramError,
    MediaNotFoundError,
    NetworkError,
    ParseError,
    RateLimitError,
)


def test_inheritance() -> None:
    assert issubclass(RateLimitError, InstagramAPIError)
    assert issubclass(MediaNotFoundError, InstagramAPIError)
    assert issubclass(AuthenticationError, InstagramAPIError)
    assert issubclass(NetworkError, InstagramError)
    assert issubclass(ParseError, InstagramError)


def test_rate_limit_error_message_and_retry() -> None:
    error = RateLimitError("rate limit exceeded", retry_after=30)
    assert "retry_after=30s" in str(error)
    assert "rate limit exceeded" in str(error)


def test_rate_limit_error_without_retry() -> None:
    error = RateLimitError("rate limit exceeded")
    assert str(error) == "rate limit exceeded"


def test_media_not_found_error_attrs_and_message() -> None:
    error = MediaNotFoundError("Video", "abc123")
    assert error.media_id == "abc123"
    assert str(error) == "Video: media_id=abc123"


def test_authentication_error_inheritance() -> None:
    error = AuthenticationError("auth failed")
    assert isinstance(error, InstagramAPIError)
    assert isinstance(error, InstagramError)


def _raise_value_error(message: str) -> None:
    raise ValueError(message)


def test_network_error_from_exception_and_context() -> None:
    exc: ValueError
    with pytest.raises(ValueError, match="boom") as ctx:
        _raise_value_error("boom")
    exc = ctx.value
    network_error = NetworkError.from_exception(exc, "http://example.com")
    assert isinstance(network_error, NetworkError)
    assert network_error.original is exc
    assert "network error requesting http://example.com: ValueError" in str(
        network_error,
    )
    assert network_error.__cause__ is exc


def test_parse_error_attributes_and_message() -> None:
    error = ParseError(
        "parse failed",
        content_type="application/json",
        preview="abcdefg",
    )
    assert error.content_type == "application/json"
    assert error.preview == "abcdefg"
    assert (
        str(error) == "parse failed | content_type=application/json | preview=abcdefg"
    )
