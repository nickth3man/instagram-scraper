from instagram_scraper.providers.stories import StoriesProvider


def test_stories_provider_requires_auth() -> None:
    provider = StoriesProvider()
    assert provider.requires_auth is True
