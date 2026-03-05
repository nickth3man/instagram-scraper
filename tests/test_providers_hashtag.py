from instagram_scraper.providers.hashtag import HashtagScrapeProvider


def test_hashtag_provider_emits_target_records() -> None:
    provider = HashtagScrapeProvider()
    targets = provider.resolve_targets(hashtag="cats", limit=2)
    assert targets
    assert all(target.target_kind == "hashtag_post" for target in targets)
