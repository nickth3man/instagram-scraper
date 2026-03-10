from datetime import UTC, datetime
from pathlib import Path

import pytest

from instagram_scraper.storage_db import (
    create_store,
    get_sync_state,
    update_sync_state,
)
from instagram_scraper.sync import (
    build_sync_target_key,
    filter_posts_by_date,
    get_latest_post_date,
    resolve_sync_targets,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path


def test_build_sync_target_key() -> None:
    assert build_sync_target_key("profile", "testuser") == "profile:testuser"
    assert build_sync_target_key("hashtag", "cats") == "hashtag:cats"
    assert build_sync_target_key("location", "nyc") == "location:nyc"


def test_get_sync_state_returns_none_for_missing_target(temp_db: Path) -> None:
    store = create_store(temp_db / "state.sqlite3")
    state = get_sync_state(store, target_key="profile:nonexistent")
    assert state is None


def test_update_sync_state_creates_new_record(temp_db: Path) -> None:
    store = create_store(temp_db / "state.sqlite3")
    sample_date = datetime(2025, 1, 1, tzinfo=UTC)

    update_sync_state(
        store,
        target_key="profile:testuser",
        last_post_date=sample_date,
        new_count=5,
    )

    state = get_sync_state(store, target_key="profile:testuser")
    assert state is not None
    assert state.last_post_date is not None
    assert state.last_post_date.year == 2025
    assert state.last_post_date.month == 1
    assert state.last_post_date.day == 1
    assert state.record_count == 5


def test_update_sync_state_accumulates_count(temp_db: Path) -> None:
    store = create_store(temp_db / "state.sqlite3")

    update_sync_state(
        store,
        target_key="profile:testuser",
        last_post_date=datetime(2025, 1, 1, tzinfo=UTC),
        new_count=5,
    )

    update_sync_state(
        store,
        target_key="profile:testuser",
        last_post_date=datetime(2025, 1, 2, tzinfo=UTC),
        new_count=3,
    )

    state = get_sync_state(store, target_key="profile:testuser")
    assert state is not None
    assert state.last_post_date is not None
    assert state.last_post_date.day == 2
    assert state.record_count == 8


def test_update_sync_state_with_none_last_post_date(temp_db: Path) -> None:
    store = create_store(temp_db / "state.sqlite3")

    update_sync_state(
        store,
        target_key="profile:testuser",
        last_post_date=None,
        new_count=3,
    )

    state = get_sync_state(store, target_key="profile:testuser")
    assert state is not None
    assert state.last_post_date is None
    assert state.record_count == 3

    update_sync_state(
        store,
        target_key="profile:testuser",
        last_post_date=datetime(2025, 1, 2, tzinfo=UTC),
        new_count=2,
    )

    state = get_sync_state(store, target_key="profile:testuser")
    assert state is not None
    assert state.last_post_date is not None
    assert state.last_post_date.day == 2
    assert state.record_count == 5


def test_filter_posts_by_date_with_none_date() -> None:
    posts: list[dict[str, object]] = [{"date_utc": datetime(2025, 1, 1, tzinfo=UTC)}]
    result = filter_posts_by_date(posts, None)
    assert result == posts


def test_filter_posts_by_date_filters_correctly() -> None:
    cutoff = datetime(2025, 1, 15, tzinfo=UTC)
    posts: list[dict[str, object]] = [
        {"date_utc": datetime(2025, 1, 10, tzinfo=UTC)},
        {"date_utc": datetime(2025, 1, 20, tzinfo=UTC)},
        {"date_utc": datetime(2025, 1, 25, tzinfo=UTC)},
    ]
    result = filter_posts_by_date(posts, cutoff)
    assert len(result) == 2


def test_filter_posts_by_date_with_string_dates() -> None:
    cutoff = datetime(2025, 1, 15, tzinfo=UTC)
    posts: list[dict[str, object]] = [
        {"date_utc": "2025-01-10T00:00:00+00:00"},
        {"date_utc": "2025-01-20T00:00:00+00:00"},
    ]
    result = filter_posts_by_date(posts, cutoff)
    assert len(result) == 1


def test_filter_posts_by_date_handles_invalid_dates() -> None:
    cutoff = datetime(2025, 1, 15, tzinfo=UTC)
    posts: list[dict[str, object]] = [
        {"date_utc": "invalid-date"},
        {"date_utc": datetime(2025, 1, 20, tzinfo=UTC)},
    ]
    result = filter_posts_by_date(posts, cutoff)
    assert len(result) == 1


def test_get_latest_post_date_with_datetime_objects() -> None:
    posts: list[dict[str, object]] = [
        {"date_utc": datetime(2025, 1, 10, tzinfo=UTC)},
        {"date_utc": datetime(2025, 1, 25, tzinfo=UTC)},
        {"date_utc": datetime(2025, 1, 15, tzinfo=UTC)},
    ]
    result = get_latest_post_date(posts)
    assert result == datetime(2025, 1, 25, tzinfo=UTC)


def test_get_latest_post_date_with_string_dates() -> None:
    posts: list[dict[str, object]] = [
        {"date_utc": "2025-01-10T00:00:00+00:00"},
        {"date_utc": "2025-01-25T00:00:00+00:00"},
    ]
    result = get_latest_post_date(posts)
    assert result == datetime(2025, 1, 25, tzinfo=UTC)


def test_get_latest_post_date_with_empty_list() -> None:
    result = get_latest_post_date([])
    assert result is None


def test_get_latest_post_date_handles_invalid_dates() -> None:
    posts: list[dict[str, object]] = [
        {"date_utc": "invalid"},
        {"date_utc": datetime(2025, 1, 20, tzinfo=UTC)},
    ]
    result = get_latest_post_date(posts)
    assert result == datetime(2025, 1, 20, tzinfo=UTC)


def test_resolve_sync_targets() -> None:
    targets = resolve_sync_targets(
        target_kind="profile",
        target_value="testuser",
        mode="sync:profile",
    )
    assert len(targets) == 1
    assert targets[0].target_kind == "profile"
    assert targets[0].target_value == "testuser"
    assert targets[0].provider == "sync"
