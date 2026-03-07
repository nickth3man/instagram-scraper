from instagram_scraper.providers.interactions import LikersProvider


def test_likers_provider_normalizes_summary() -> None:
    provider = LikersProvider()
    summary = provider.run(username="example")
    assert summary.mode == "likers"
