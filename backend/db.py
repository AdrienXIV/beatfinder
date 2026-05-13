"""SQLAlchemy engine + session factory.

Engine SQLite par défaut sur DATA_DIR/analyses.db. `init_db()` crée les tables
si elles n'existent pas (idempotent).
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .domain.models import Base


def get_database_url(data_dir: Path | str | None = None) -> str:
    if data_dir is None:
        data_dir = get_settings().data_dir
    db_path = Path(data_dir) / "analyses.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_database_url(), echo=False, future=True)


def init_db(engine: Engine | None = None) -> Engine:
    """Crée les tables si absentes. Idempotent. À appeler au boot."""
    engine = engine or make_engine()
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(
    engine: Engine | None = None,
) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine or make_engine(), expire_on_commit=False, future=True,
    )
