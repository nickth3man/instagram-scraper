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
    e = RateLimitError("rate limit exceeded", retry_after=30)
    assert "retry_after=30s" in str(e)
    assert "rate limit exceeded" in str(e)


def test_rate_limit_error_without_retry() -> None:
    e = RateLimitError("rate limit exceeded")
    assert str(e) == "rate limit exceeded"


def test_media_not_found_error_attrs_and_message() -> None:
    e = MediaNotFoundError("Video", "abc123")
    assert e.media_id == "abc123"
    assert str(e) == "Video: media_id=abc123"


def test_authentication_error_inheritance() -> None:
    e = AuthenticationError("auth failed")
    assert isinstance(e, InstagramAPIError)
    assert isinstance(e, InstagramError)


def test_network_error_from_exception_and_context() -> None:
    try:
        raise ValueError("boom")
    except ValueError as exc:
        ne = NetworkError.from_exception(exc, "http://example.com")
        assert isinstance(ne, NetworkError)
        assert ne.original is exc
        assert "network error requesting http://example.com: ValueError" in str(ne)
        assert ne.__cause__ is exc


def test_parse_error_attributes_and_message() -> None:
    e = ParseError("parse failed", content_type="application/json", preview="abcdefg")
    assert e.content_type == "application/json"
    assert e.preview == "abcdefg"
    assert str(e) == "parse failed | content_type=application/json | preview=abcdefg"
