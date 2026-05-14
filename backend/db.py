"""SQLAlchemy engine + session factory + migrations idempotentes.

Engine SQLite par défaut sur DATA_DIR/analyses.db. `init_db()` crée les tables
manquantes via `Base.metadata.create_all()` puis applique les migrations de
colonnes (ALTER TABLE ADD COLUMN si absente).

**Important** : pas d'Alembic ici. Les migrations sont déclarées en dur dans
`PENDING_COLUMN_MIGRATIONS` et tournent à chaque boot — idempotentes (test
de présence avant ALTER). À chaque ajout de colonne dans `domain/models.py`,
ajouter une entrée correspondante ici, sinon les utilisateurs qui upgradent
auront une exception "no such column" au premier requête.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .domain.models import Base

log = logging.getLogger(__name__)


# Migrations idempotentes : (table_name, column_name, sql_definition).
# sql_definition est passé tel quel à ALTER TABLE ... ADD COLUMN — doit être
# nullable OU avoir un DEFAULT (contrainte SQLite ALTER TABLE).
#
# Ordre chronologique d'ajout (juste pour l'historique humain — pas requis).
PENDING_COLUMN_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    # v1.8.0 — État draft/locked des sessions créatives
    ("creative_sessions", "is_locked", "BOOLEAN DEFAULT 0 NOT NULL"),
    ("creative_sessions", "locked_at", "DATETIME"),
)


def get_database_url(data_dir: Path | str | None = None) -> str:
    if data_dir is None:
        data_dir = get_settings().data_dir
    db_path = Path(data_dir) / "analyses.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_database_url(), echo=False, future=True)


def _migrate_columns(engine: Engine) -> None:
    """Applique les ALTER TABLE manquants pour les colonnes attendues.

    Idempotent : check la présence de chaque colonne via PRAGMA avant ALTER.
    Ignore les tables absentes (create_all les créera avec la bonne struct).
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table_name, col_name, col_def in PENDING_COLUMN_MIGRATIONS:
        if table_name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        if col_name in existing_cols:
            continue
        with engine.begin() as conn:
            conn.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"),
            )
        log.info(
            "DB migration applied : %s.%s added (%s)",
            table_name, col_name, col_def,
        )


def init_db(engine: Engine | None = None) -> Engine:
    """Crée les tables manquantes + applique les migrations de colonnes.

    Idempotent. À appeler au boot. Sans cette étape, les utilisateurs qui
    upgradent Beatfinder vers une version avec une nouvelle colonne auront
    une exception au premier requête sur la table impactée.
    """
    engine = engine or make_engine()
    Base.metadata.create_all(engine)
    _migrate_columns(engine)
    return engine


def make_session_factory(
    engine: Engine | None = None,
) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine or make_engine(), expire_on_commit=False, future=True,
    )
