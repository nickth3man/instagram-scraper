from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from instagram_scraper.config import (
    HasOutputDir,
    HasRetryConfig,
    HttpConfig,
    OutputConfig,
    RetryConfig,
    ScraperConfig,
)


def test_retry_config_defaults_and_frozen() -> None:
    retry_config = RetryConfig()
    assert isinstance(retry_config, RetryConfig)
    # defaults
    assert retry_config.timeout == 30
    assert retry_config.max_retries == 3
    assert retry_config.min_delay == pytest.approx(0.05)
    assert retry_config.max_delay == pytest.approx(0.2)
    assert retry_config.base_retry_seconds == pytest.approx(1.0)
    # frozen dataclass: cannot assign
    with pytest.raises(FrozenInstanceError):
        retry_config.timeout = 40  # type: ignore[misc]


def test_http_config_includes_retry_via_property() -> None:
    http_config = HttpConfig()
    r = http_config.retry
    assert isinstance(r, RetryConfig)
    assert r.timeout == http_config.timeout
    assert r.max_retries == http_config.max_retries
    assert r.min_delay == http_config.min_delay
    assert r.max_delay == http_config.max_delay


def test_output_config_defaults() -> None:
    output_config = OutputConfig()
    assert output_config.output_dir == Path("data")
    assert output_config.should_reset_output is False
    assert output_config.checkpoint_every == 20


def test_scraper_config_composition() -> None:
    scraper_config = ScraperConfig()
    assert isinstance(scraper_config.http, HttpConfig)
    assert isinstance(scraper_config.output, OutputConfig)
    assert scraper_config.should_resume is False
    assert scraper_config.limit is None


def test_has_retry_config_protocol() -> None:
    assert isinstance(HttpConfig(), HasRetryConfig)


def test_has_output_dir_protocol() -> None:
    assert isinstance(OutputConfig(), HasOutputDir)
