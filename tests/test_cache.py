from pathlib import Path

from instagram_scraper.storage.cache import ScraperCache


def test_scraper_cache_round_trips_values(tmp_path: Path) -> None:
    with ScraperCache(tmp_path / "cache") as cache:
        cache.set("profile:example", {"seen": True})
        assert cache.get("profile:example") == {"seen": True}
