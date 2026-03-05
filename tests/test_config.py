from pathlib import Path

from instagram_scraper.config import AppConfig


def test_app_config_defaults_output_dir_to_data() -> None:
    config = AppConfig()
    assert config.output_dir == Path("data")
    assert config.limit is None
