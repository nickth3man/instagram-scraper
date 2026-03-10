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


def create_store(path: Path) -> MetadataStore:
    """Create a metadata store backed by the given SQLite file.

    Returns
    -------
    MetadataStore
        A ready-to-use metadata store instance.

    """
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return MetadataStore(engine=engine)


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
