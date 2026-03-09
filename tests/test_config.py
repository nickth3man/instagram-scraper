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
    rc = RetryConfig()
    assert isinstance(rc, RetryConfig)
    # defaults
    assert rc.timeout == 30
    assert rc.max_retries == 3
    assert rc.min_delay == 0.05
    assert rc.max_delay == 0.2
    assert rc.base_retry_seconds == 1.0
    # frozen dataclass: cannot assign
    with pytest.raises(FrozenInstanceError):
        rc.timeout = 40  # type: ignore


def test_http_config_includes_retry_via_property() -> None:
    hc = HttpConfig()
    r = hc.retry
    assert isinstance(r, RetryConfig)
    assert r.timeout == hc.timeout
    assert r.max_retries == hc.max_retries
    assert r.min_delay == hc.min_delay
    assert r.max_delay == hc.max_delay


def test_output_config_defaults() -> None:
    oc = OutputConfig()
    assert oc.output_dir == Path("data")
    assert oc.reset_output is False
    assert oc.checkpoint_every == 20


def test_scraper_config_composition() -> None:
    sc = ScraperConfig()
    assert isinstance(sc.http, HttpConfig)
    assert isinstance(sc.output, OutputConfig)
    assert sc.resume is False
    assert sc.limit is None


def test_has_retry_config_protocol() -> None:
    assert isinstance(HttpConfig(), HasRetryConfig)


def test_has_output_dir_protocol() -> None:
    assert isinstance(OutputConfig(), HasOutputDir)
