from instagram_scraper.providers.follow_graph import FollowGraphProvider


def test_followers_provider_marks_mode_experimental() -> None:
    provider = FollowGraphProvider()
    info = provider.describe_mode("followers")
    assert info.support_tier == "experimental"
