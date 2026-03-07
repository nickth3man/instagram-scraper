from instagram_scraper.providers.location import LocationScrapeProvider


def test_location_provider_emits_target_records() -> None:
    provider = LocationScrapeProvider()
    targets = provider.resolve_targets(location="new-york", limit=2)
    assert targets
    assert all(target.target_kind == "location_post" for target in targets)
