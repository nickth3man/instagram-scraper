import pytest

from instagram_scraper.capabilities import ensure_mode_is_runnable


def test_hashtag_requires_auth() -> None:
    with pytest.raises(RuntimeError, match="requires authentication"):
        ensure_mode_is_runnable("hashtag", has_auth=False)
