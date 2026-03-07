# Copyright (c) 2026
"""SQLite-backed metadata store for normalized scrape targets."""

from __future__ import annotations

from dataclasses import dataclass
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
