from instagram_scraper.filters import should_keep_user


def test_should_keep_user_rejects_private_when_requested() -> None:
    assert should_keep_user(
        {"is_private": True, "followers": 10, "following": 20},
        skip_private=True,
    ) is False
