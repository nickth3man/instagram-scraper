from instagram_scraper.error_codes import (
    ErrorCode,
    error_code_from_exception,
    error_code_from_status,
)


def test_error_code_values() -> None:
    expected = {
        "HTTP_400": "http_400",
        "HTTP_401": "http_401",
        "HTTP_403": "http_403",
        "HTTP_404": "http_404",
        "HTTP_429": "http_429",
        "HTTP_500": "http_500",
        "HTTP_502": "http_502",
        "HTTP_503": "http_503",
        "HTTP_504": "http_504",
        "HTTP_UNKNOWN": "http_unknown",
        "NETWORK_TIMEOUT": "network_timeout",
        "NETWORK_CONNECTION": "network_connection",
        "NETWORK_DNS": "network_dns",
        "NETWORK_SSL": "network_ssl",
        "NETWORK_UNKNOWN": "network_unknown",
        "MEDIA_NOT_FOUND": "media_not_found",
        "MEDIA_INFO_EMPTY": "media_info_empty",
        "MEDIA_INFO_INVALID": "media_info_invalid",
        "AUTHENTICATION_FAILED": "authentication_failed",
        "RATE_LIMITED": "rate_limited",
        "PARSE_NON_JSON": "parse_non_json",
        "PARSE_JSON_DECODE": "parse_json_decode",
        "PARSE_INVALID_SHAPE": "parse_invalid_shape",
        "FILE_WRITE_ERROR": "file_write_error",
        "FILE_READ_ERROR": "file_read_error",
        "FILE_EMPTY": "file_empty",
        "INVALID_ARTIFACT": "invalid_artifact",
        "AUDIT_FAILURE": "audit_failure",
        "MISSING_EXPORT_FILE": "missing_export_file",
        "INPUT_MISSING_SHORTCODE": "input_missing_shortcode",
        "INPUT_MISSING_MEDIA_ID": "input_missing_media_id",
        "INPUT_INVALID_URL": "input_invalid_url",
        "UNKNOWN": "unknown",
        "REQUEST_FAILED": "request_failed",
    }
    for member in ErrorCode:
        assert member.value == expected[member.name]


def test_error_code_from_status() -> None:
    assert error_code_from_status(429) == ErrorCode.HTTP_429
    assert error_code_from_status(500) == ErrorCode.HTTP_500
    assert error_code_from_status(502) == ErrorCode.HTTP_502
    assert error_code_from_status(503) == ErrorCode.HTTP_503
    assert error_code_from_status(504) == ErrorCode.HTTP_504
    assert error_code_from_status(999) == ErrorCode.HTTP_UNKNOWN


def test_error_code_from_exception() -> None:
    assert error_code_from_exception(TimeoutError()) == ErrorCode.NETWORK_TIMEOUT
    assert error_code_from_exception(ConnectionError()) == ErrorCode.NETWORK_CONNECTION
    assert error_code_from_exception(ValueError()) == ErrorCode.UNKNOWN
