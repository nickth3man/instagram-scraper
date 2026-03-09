import io
import json
import logging

from instagram_scraper import logging_config


def test_configure_logging_returns_root_logger() -> None:
    root = logging_config.configure_logging()
    assert isinstance(root, logging.Logger)
    assert root is logging.getLogger()


def test_get_logger_returns_named_logger() -> None:
    logger = logging_config.get_logger("my_named_logger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "my_named_logger"


def test_log_context_adds_context_fields() -> None:
    stream = io.StringIO()
    logging_config.configure_logging(level="INFO", json_format=True, stream=stream)
    logger = logging_config.get_logger("testlogger")
    with logging_config.LogContext(request_id="abc123"):
        logger.info("processing")
    contents = stream.getvalue().strip().splitlines()
    assert len(contents) == 1
    data = json.loads(contents[0])
    assert data.get("level") == "INFO"
    assert data.get("logger") == "testlogger"
    assert data.get("request_id") == "abc123"
    assert data.get("message") == "processing"


def test_log_context_nested_merges_fields() -> None:
    stream = io.StringIO()
    logging_config.configure_logging(level="INFO", json_format=True, stream=stream)
    logger = logging_config.get_logger("nestedlogger")
    with logging_config.LogContext(request_id="outer"):
        logger.info("outer")
        with logging_config.LogContext(user="alice"):
            logger.info("inner")
    lines = stream.getvalue().strip().splitlines()
    assert len(lines) >= 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first.get("request_id") == "outer"
    assert "user" not in first
    assert second.get("request_id") == "outer"
    assert second.get("user") == "alice"
