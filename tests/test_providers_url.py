from instagram_scraper.providers.url import UrlScrapeProvider


def test_url_provider_normalizes_summary() -> None:
    provider = UrlScrapeProvider()
    summary = provider.run(post_url="https://www.instagram.com/p/example/")
    assert summary.mode == "url"
