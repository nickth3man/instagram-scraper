from pathlib import Path

import pytest

from instagram_scraper.config import AppConfig


def test_app_config_defaults_output_dir_to_data() -> None:
    config = AppConfig()
    assert config.output_dir == Path("data")
    assert config.limit is None


def test_app_config_includes_shared_runtime_controls() -> None:
    config = AppConfig()
    assert config.raw_captures is False
    assert config.request_timeout == 30
    assert config.max_retries == 5
    assert config.min_delay == pytest.approx(0.05)
    assert config.max_delay == pytest.approx(0.2)
    assert config.checkpoint_every == 20
