# Copyright (c) 2026
"""Custom exception hierarchy for Instagram scraper operations.

This module defines domain-specific exceptions that replace string error codes
with typed, structured error handling.
"""

from __future__ import annotations

from typing import Self

from instagram_scraper.error_codes import ErrorCode


class InstagramError(Exception):
    """Base exception for all Instagram scraper errors.

    All custom exceptions in this package inherit from this class,
    allowing callers to catch all scraper-specific errors with a single
    except clause.
    """

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode = ErrorCode.UNKNOWN,
    ) -> None:
        """Initialize base InstagramError with a message."""
        self.code = code
        super().__init__(message)


class InstagramAPIError(InstagramError):
    """Base for errors returned by Instagram's API.

    These errors indicate the API responded but indicated a problem
    (rate limits, missing content, authentication issues, etc.).
    """

    def __init__(self, message: str) -> None:
        """Initialize InstagramAPIError with a message."""
        super().__init__(message)


class RateLimitError(InstagramAPIError):
    """Instagram API rate limit exceeded.

    Attributes
    ----------
    retry_after : int | None
        Seconds to wait before retrying, if provided by Instagram.

    """

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        """Initialize RateLimitError with an optional retry_after hint."""
        self.retry_after = retry_after
        full_message = f"{message}" + (
            f" (retry_after={retry_after}s)" if retry_after else ""
        )
        super().__init__(full_message)


class MediaNotFoundError(InstagramAPIError):
    """Requested media does not exist or is unavailable.

    Attributes
    ----------
    media_id : str
        The media identifier that was not found.

    """

    def __init__(self, context: str, media_id: str) -> None:
        """Initialize MediaNotFoundError with context and media_id."""
        self.media_id = media_id
        super().__init__(f"{context}: media_id={media_id}")


class AuthenticationError(InstagramAPIError):
    """Authentication failed or credentials are invalid."""

    def __init__(self, message: str) -> None:
        """Initialize AuthenticationError with a message."""
        super().__init__(message)


class NetworkError(InstagramError):
    """Network-level error during HTTP request.

    Wraps lower-level exceptions (timeout, connection errors) with
    domain context while preserving the original exception for debugging.

    Attributes
    ----------
    original : Exception | None
        The underlying exception that caused this error.

    """

    def __init__(
        self,
        message: str,
        *,
        original: Exception | None = None,
    ) -> None:
        """Initialize NetworkError with a message and optional original exception."""
        self.original = original
        super().__init__(message)
        if original is not None:
            self.__cause__ = original

    @classmethod
    def from_exception(cls, exc: Exception, url: str) -> Self:
        """Create NetworkError wrapping an existing exception.

        Parameters
        ----------
        exc : Exception
            The original exception (e.g., requests.Timeout).
        url : str
            The URL that was being requested.

        Returns
        -------
        NetworkError
            A new NetworkError with context.

        """
        return cls(
            f"network error requesting {url}: {exc.__class__.__name__}",
            original=exc,
        )


class ParseError(InstagramError):
    """Failed to parse API response.

    Attributes
    ----------
    content_type : str | None
        The Content-Type header of the response.
    preview : str | None
        A sanitized preview of the response content.

    """

    def __init__(
        self,
        message: str,
        *,
        content_type: str | None = None,
        preview: str | None = None,
    ) -> None:
        """Initialize ParseError with optional content_type and preview."""
        self.content_type = content_type
        self.preview = preview
        parts = [message]
        if content_type:
            parts.append(f"content_type={content_type}")
        if preview:
            parts.append(f"preview={preview[:50]}")
        super().__init__(" | ".join(parts))
