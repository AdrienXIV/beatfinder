"""Fixtures pytest partagées.

Pas de TestClient FastAPI ici (besoin de httpx). Les fixtures couvrent les
besoins unitaires : DB SQLite isolée, dossier data temporaire, settings forcé.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import Settings, get_settings
from backend.domain.models import Base


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Iterator[Path]:
    """Bust le cache get_settings + force data_dir vers un tmpdir pour ce test."""
    original = get_settings.cache_clear
    get_settings.cache_clear()
    # Inject l'env DATA_DIR : pydantic-settings le lira au prochain get_settings()
    import os
    prev = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = str(tmp_path)
    try:
        yield tmp_path
    finally:
        if prev is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = prev
        get_settings.cache_clear()
        # Touch original pour bypasser warn unused-ignores
        _ = original


@pytest.fixture
def session() -> Iterator[Session]:
    """Session SQLite en mémoire avec schéma initialisé. Isolée par test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as s:
        yield s
    engine.dispose()


@pytest.fixture
def fresh_settings(tmp_data_dir: Path) -> Settings:
    """Settings recréé après mutation env. Pour tests qui veulent lire la config."""
    return get_settings()
