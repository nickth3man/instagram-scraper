import sqlite3
from pathlib import Path

import pytest

from instagram_scraper.storage.database import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_VERSION_KEY,
    create_store,
    record_target,
)


def test_record_target_upserts_by_normalized_key(tmp_path: Path) -> None:
    store = create_store(tmp_path / "state.sqlite3")
    record_target(store, kind="profile", normalized_key="profile:example")
    record_target(store, kind="profile", normalized_key="profile:example")
    assert store.count_targets() == 1


def test_create_store_initializes_schema_version(tmp_path: Path) -> None:
    store = create_store(tmp_path / "state.sqlite3")

    assert store.schema_version() == CURRENT_SCHEMA_VERSION


def test_create_store_bootstraps_legacy_database_without_metadata(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        "CREATE TABLE targets ("
        "id INTEGER PRIMARY KEY, "
        "kind TEXT, "
        "normalized_key TEXT UNIQUE"
        ")",
    )
    connection.execute(
        "CREATE TABLE sync_state ("
        "target_key TEXT PRIMARY KEY, "
        "last_scraped_at TEXT, "
        "last_post_date TEXT, "
        "record_count INTEGER, "
        "created_at TEXT, "
        "updated_at TEXT"
        ")",
    )
    connection.commit()
    connection.close()

    store = create_store(database_path)

    assert store.schema_version() == CURRENT_SCHEMA_VERSION


def test_create_store_rejects_future_schema_version(tmp_path: Path) -> None:
    database_path = tmp_path / "future.sqlite3"
    create_store(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE store_metadata SET value = ? WHERE key = ?",
            ("999", SCHEMA_VERSION_KEY),
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="Unsupported schema version"):
        create_store(database_path)
