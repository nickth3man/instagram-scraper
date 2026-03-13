# Copyright (c) 2026
"""Standardized error codes for Instagram scraper operations.

This module replaces ad-hoc string error codes with an enum, ensuring
consistent error identification across the codebase.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet


class ErrorCode(StrEnum):
    """Standardized error codes for scraper operations.

    Error codes are stable identifiers that can be used for:
    - Log filtering and alerting
    - Error categorization in dashboards
    - Programmatic error handling

    The string value is suitable for serialization (CSV, JSON, logs).
    """

    # HTTP Status Errors
    HTTP_400 = "http_400"
    HTTP_401 = "http_401"
    HTTP_403 = "http_403"
    HTTP_404 = "http_404"
    HTTP_429 = "http_429"
    HTTP_500 = "http_500"
    HTTP_502 = "http_502"
    HTTP_503 = "http_503"
    HTTP_504 = "http_504"
    HTTP_UNKNOWN = "http_unknown"

    # Network Errors
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_CONNECTION = "network_connection"
    NETWORK_DNS = "network_dns"
    NETWORK_SSL = "network_ssl"
    NETWORK_UNKNOWN = "network_unknown"

    # API Errors
    MEDIA_NOT_FOUND = "media_not_found"
    MEDIA_INFO_EMPTY = "media_info_empty"
    MEDIA_INFO_INVALID = "media_info_invalid"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"

    # Parse Errors
    PARSE_NON_JSON = "parse_non_json"
    PARSE_JSON_DECODE = "parse_json_decode"
    PARSE_INVALID_SHAPE = "parse_invalid_shape"

    # File Errors
    FILE_WRITE_ERROR = "file_write_error"
    FILE_READ_ERROR = "file_read_error"
    FILE_EMPTY = "file_empty"
    INVALID_ARTIFACT = "invalid_artifact"
    AUDIT_FAILURE = "audit_failure"
    MISSING_EXPORT_FILE = "missing_export_file"

    # Input Errors
    INPUT_MISSING_SHORTCODE = "input_missing_shortcode"
    INPUT_MISSING_MEDIA_ID = "input_missing_media_id"
    INPUT_INVALID_URL = "input_invalid_url"

    # Generic
    UNKNOWN = "unknown"
    REQUEST_FAILED = "request_failed"


# Mapping of HTTP status codes to ErrorCode
_STATUS_TO_ERROR: dict[int, ErrorCode] = {
    400: ErrorCode.HTTP_400,
    401: ErrorCode.HTTP_401,
    403: ErrorCode.HTTP_403,
    404: ErrorCode.HTTP_404,
    429: ErrorCode.HTTP_429,
    500: ErrorCode.HTTP_500,
    502: ErrorCode.HTTP_502,
    503: ErrorCode.HTTP_503,
    504: ErrorCode.HTTP_504,
}

# Status codes that indicate retryable errors
RETRYABLE_STATUS_CODES: AbstractSet[int] = {429, 500, 502, 503, 504}


def error_code_from_status(status_code: int) -> ErrorCode:
    """Convert HTTP status code to ErrorCode.

    Parameters
    ----------
    status_code : int
        HTTP response status code.

    Returns
    -------
    ErrorCode
        The corresponding error code.

    """
    return _STATUS_TO_ERROR.get(status_code, ErrorCode.HTTP_UNKNOWN)


# Mapping of exception types to ErrorCode
_EXCEPTION_TO_ERROR: dict[type[Exception], ErrorCode] = {
    TimeoutError: ErrorCode.NETWORK_TIMEOUT,
    ConnectionError: ErrorCode.NETWORK_CONNECTION,
}


def error_code_from_exception(exc: Exception) -> ErrorCode:
    """Convert exception type to ErrorCode.

    Parameters
    ----------
    exc : Exception
        The exception that occurred.

    Returns
    -------
    ErrorCode
        The corresponding error code.

    """
    exc_type = type(exc)

    # Check exact type match
    if exc_type in _EXCEPTION_TO_ERROR:
        return _EXCEPTION_TO_ERROR[exc_type]

    # Check base classes
    for exc_class, code in _EXCEPTION_TO_ERROR.items():
        if isinstance(exc, exc_class):
            return code

    return ErrorCode.UNKNOWN
