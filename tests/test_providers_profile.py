from instagram_scraper.providers.profile import ProfileScrapeProvider


def test_profile_provider_normalizes_summary() -> None:
    provider = ProfileScrapeProvider()
    summary = provider.run(username="example")
    assert summary.mode == "profile"
