from pathlib import Path

from instagram_scraper.storage_db import create_store, record_target


def test_record_target_upserts_by_normalized_key(tmp_path: Path) -> None:
    store = create_store(tmp_path / "state.sqlite3")
    record_target(store, kind="profile", normalized_key="profile:example")
    record_target(store, kind="profile", normalized_key="profile:example")
    assert store.count_targets() == 1
