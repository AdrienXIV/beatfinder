"""Configuration centralisée — env vars + defaults.

Source unique pour tout ce que les modules backend lisent depuis l'env (DATA_DIR,
LOG_LEVEL, credentials Spotify, BEATFINDER_*). Pydantic-settings lit
automatiquement le `.env` et les env vars système.

Usage typique :
    from backend.config import get_settings
    settings = get_settings()
    audio_cache = settings.data_dir / "audio"

`get_settings()` est cached — instanciation une seule fois par process. Les
tests peuvent forcer un reload via `get_settings.cache_clear()`.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Final

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

IS_PACKAGED: Final[bool] = (
    getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")
)


def _default_data_dir() -> Path:
    """En mode binaire PyInstaller, écrit dans `~/.beatfinder/data` (portable).
    En mode dev (source), garde `./data` relatif au cwd."""
    if IS_PACKAGED:
        return Path.home() / ".beatfinder" / "data"
    return Path("./data")


class Settings(BaseSettings):
    """Configuration globale lue depuis l'env + `.env`.

    Les noms en `snake_case` correspondent aux env vars en `UPPER_SNAKE_CASE`
    (pydantic-settings fait la conversion automatique).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Storage
    data_dir: Path = Field(default_factory=_default_data_dir)
    log_level: str = "INFO"

    # Serveur standalone (mode binaire)
    beatfinder_host: str = "127.0.0.1"
    beatfinder_port: int = 8000
    beatfinder_no_auto_open: bool = False

    # Spotify OAuth
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = ""
    spotify_cache_path: Path | None = None

    # YouTube cookies (optionnel, contourne géo/âge blocks)
    yt_dlp_cookies_file: Path | None = None

    @field_validator("yt_dlp_cookies_file", "spotify_cache_path", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v: object) -> object:
        """Convertit les `VAR=` vides du `.env` en None (sinon Path("") → Path("."))."""
        if isinstance(v, str) and not v.strip():
            return None
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor. Cache busté par `get_settings.cache_clear()`."""
    return Settings()
