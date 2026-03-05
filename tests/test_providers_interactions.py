from instagram_scraper.providers.interactions import LikersProvider


def test_likers_provider_normalizes_summary() -> None:
    provider = LikersProvider()
    summary = provider.run()
    assert summary.mode == "likers"
