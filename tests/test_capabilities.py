import pytest

from instagram_scraper.core.capabilities import (
    describe_mode_capability,
    ensure_mode_is_runnable,
)


def test_mode_capability_marks_profile_stable() -> None:
    descriptor = describe_mode_capability("profile")
    assert descriptor.support_tier == "stable"
    assert descriptor.requires_auth is False


def test_hashtag_requires_auth() -> None:
    with pytest.raises(RuntimeError, match="requires authentication"):
        ensure_mode_is_runnable("hashtag", has_auth=False)
