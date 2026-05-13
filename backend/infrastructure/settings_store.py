"""Préférences utilisateur persistées dans `data/settings.json`.

Stocke pour l'instant : credentials Spotify (client_id + client_secret +
redirect_uri optionnel). Les credentials sont en clair — c'est une app desktop
locale, le fichier reste sur la machine de l'utilisateur.

Lecture defensive (absent/corrompu → defaults). Écriture atomique.
Fallback sur les variables d'environnement (`.env`) si pas dans le JSON, pour
ne pas casser les setups existants.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from backend.config import get_settings

log = logging.getLogger("backend.settings_store")

SETTINGS_FILENAME: Final[str] = "settings.json"


@dataclass(slots=True)
class SpotifyCreds:
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id.strip()) and bool(self.client_secret.strip())


@dataclass(slots=True)
class Settings:
    spotify: SpotifyCreds

    def to_dict(self) -> dict[str, Any]:
        return {"spotify": asdict(self.spotify)}


def settings_path(data_dir: Path | None = None) -> Path:
    if data_dir is None:
        data_dir = get_settings().data_dir
    return data_dir / SETTINGS_FILENAME


def _spotify_from_env() -> SpotifyCreds:
    s = get_settings()
    return SpotifyCreds(
        client_id=s.spotify_client_id.strip(),
        client_secret=s.spotify_client_secret.strip(),
        redirect_uri=s.spotify_redirect_uri.strip(),
    )


def load_settings(data_dir: Path | None = None) -> Settings:
    """Lit le fichier. Defaults via env si absent/corrompu."""
    path = settings_path(data_dir)
    env_creds = _spotify_from_env()

    if not path.is_file():
        return Settings(spotify=env_creds)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        log.warning("Corrupt settings file %s, returning env defaults", path)
        return Settings(spotify=env_creds)

    if not isinstance(payload, dict):
        return Settings(spotify=env_creds)

    s_raw = payload.get("spotify") or {}
    # Merge : valeurs du fichier sinon env
    spotify = SpotifyCreds(
        client_id=(s_raw.get("client_id") or env_creds.client_id or "").strip(),
        client_secret=(
            s_raw.get("client_secret") or env_creds.client_secret or ""
        ).strip(),
        redirect_uri=(
            s_raw.get("redirect_uri") or env_creds.redirect_uri or ""
        ).strip(),
    )
    return Settings(spotify=spotify)


def save_spotify(creds: SpotifyCreds, data_dir: Path | None = None) -> Settings:
    """Écriture atomique. Retourne la config résolue après merge."""
    path = settings_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    current = load_settings(data_dir)
    merged = SpotifyCreds(
        client_id=creds.client_id.strip() or current.spotify.client_id,
        client_secret=creds.client_secret.strip() or current.spotify.client_secret,
        redirect_uri=creds.redirect_uri.strip() or current.spotify.redirect_uri,
    )

    payload = {"spotify": asdict(merged)}
    fd, tmp_name = tempfile.mkstemp(
        prefix=".settings_", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return Settings(spotify=merged)


def clear_spotify(data_dir: Path | None = None) -> Settings:
    """Supprime les credentials Spotify du JSON. Garde l'env comme fallback."""
    path = settings_path(data_dir)
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and "spotify" in payload:
                payload["spotify"] = {
                    "client_id": "",
                    "client_secret": "",
                    "redirect_uri": "",
                }
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except (json.JSONDecodeError, OSError):
            pass
    return load_settings(data_dir)
