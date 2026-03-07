from pathlib import Path

import pytest

from instagram_scraper.scrape_instagram_from_browser_dump import run_url_scrape


def test_run_url_scrape_rejects_non_instagram_urls(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Instagram"):
        run_url_scrape(
            urls=["https://example.com/internal"],
            output_dir=tmp_path,
            cookie_header="sessionid=abc",
        )
