from pathlib import Path

from instagram_scraper.cache import ScraperCache


def test_scraper_cache_round_trips_values(tmp_path: Path) -> None:
    cache = ScraperCache(tmp_path / "cache")
    cache.set("profile:example", {"seen": True})
    assert cache.get("profile:example") == {"seen": True}
