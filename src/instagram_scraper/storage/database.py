# Copyright (c) 2026
"""SQLite-backed metadata store for normalized scrape targets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine import Engine


class Base(DeclarativeBase):
    """Base class for store ORM models."""


SCHEMA_VERSION_KEY = "schema_version"
CURRENT_SCHEMA_VERSION = 1


class StoreMetadata(Base):
    """Small key/value metadata rows for schema governance."""

    __tablename__ = "store_metadata"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))


class TargetState(Base):
    """Stored support-state record for a normalized target."""

    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]
    normalized_key: Mapped[str] = mapped_column(String(255), unique=True)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SyncState(Base):
    """Sync state for incremental scraping."""

    __tablename__ = "sync_state"

    # This is intentionally not a foreign key to ``TargetState.normalized_key``.
    # Sync bookkeeping must be able to track a target before or independently of
    # any normalized target rows written during one-shot pipelines.
    target_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_scraped_at: Mapped[datetime | None]
    last_post_date: Mapped[datetime | None]
    record_count: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        onupdate=_utcnow,
    )


@dataclass(frozen=True)
class MetadataStore:
    """Small wrapper around a SQLite engine for scraper state."""

    engine: Engine

    def count_targets(self) -> int:
        """Return the total number of unique stored targets.

        Returns
        -------
        int
            The number of unique normalized targets in the store.

        """
        with Session(self.engine) as session:
            return session.scalar(select(func.count()).select_from(TargetState)) or 0

    def schema_version(self) -> int:
        """Return the current schema version recorded in the store.

        Returns
        -------
        int
            The integer schema version stored in SQLite metadata.

        """
        return _detect_schema_version(self.engine)


def create_store(path: Path) -> MetadataStore:
    """Create a metadata store backed by the given SQLite file.

    Returns
    -------
    MetadataStore
        A ready-to-use metadata store instance.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}")
    _bootstrap_schema(engine)
    return MetadataStore(engine=engine)


def _bootstrap_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    existing_version = _detect_schema_version_or_none(engine)
    if existing_version is None:
        _set_schema_version(engine, CURRENT_SCHEMA_VERSION)
        return
    if existing_version > CURRENT_SCHEMA_VERSION:
        message = (
            "Unsupported schema version "
            f"{existing_version}; current version is {CURRENT_SCHEMA_VERSION}"
        )
        raise RuntimeError(message)
    if existing_version < CURRENT_SCHEMA_VERSION:
        _migrate_schema(engine, existing_version)


def _detect_schema_version(engine: Engine) -> int:
    version = _detect_schema_version_or_none(engine)
    if version is None:
        message = "Schema version metadata is missing"
        raise RuntimeError(message)
    return version


def _detect_schema_version_or_none(engine: Engine) -> int | None:
    with Session(engine) as session:
        record = session.get(StoreMetadata, SCHEMA_VERSION_KEY)
        if record is None:
            return None
        try:
            return int(record.value)
        except ValueError as exc:
            message = f"Invalid schema version metadata: {record.value!r}"
            raise RuntimeError(message) from exc


def _set_schema_version(engine: Engine, version: int) -> None:
    with Session(engine) as session:
        record = session.get(StoreMetadata, SCHEMA_VERSION_KEY)
        if record is None:
            session.add(StoreMetadata(key=SCHEMA_VERSION_KEY, value=str(version)))
        else:
            record.value = str(version)
        session.commit()


def _migrate_schema(engine: Engine, current_version: int) -> None:
    if current_version == CURRENT_SCHEMA_VERSION:
        return
    if current_version < CURRENT_SCHEMA_VERSION:
        _set_schema_version(engine, CURRENT_SCHEMA_VERSION)
        return
    message = f"Unsupported schema migration path from version {current_version}"
    raise RuntimeError(message)


def record_target(store: MetadataStore, *, kind: str, normalized_key: str) -> None:
    """Insert or update a target record by normalized key."""
    with Session(store.engine) as session:
        existing = session.scalar(
            select(TargetState).where(TargetState.normalized_key == normalized_key),
        )
        if existing is None:
            session.add(TargetState(kind=kind, normalized_key=normalized_key))
        else:
            existing.kind = kind
        session.commit()


def get_sync_state(store: MetadataStore, *, target_key: str) -> SyncState | None:
    """Retrieve sync state for a target if it exists.

    Returns
    -------
    SyncState | None
        The sync state record or None if this is the first sync.

    """
    with Session(store.engine) as session:
        return session.scalar(
            select(SyncState).where(SyncState.target_key == target_key),
        )


def update_sync_state(
    store: MetadataStore,
    *,
    target_key: str,
    last_post_date: datetime | None,
    new_count: int,
) -> None:
    """Insert or update sync state after a successful sync."""
    with Session(store.engine) as session:
        existing = session.scalar(
            select(SyncState).where(SyncState.target_key == target_key),
        )
        now = _utcnow()
        if existing is None:
            session.add(
                SyncState(
                    target_key=target_key,
                    last_scraped_at=now,
                    last_post_date=last_post_date,
                    record_count=new_count,
                ),
            )
        else:
            existing.last_scraped_at = now
            if last_post_date is not None:
                existing.last_post_date = last_post_date
            existing.record_count += new_count
            existing.updated_at = now
        session.commit()
