"""Presets de patterns industry-standard pour le plan d'action.

Permet de comparer une track/playlist à des médianes mainstream (Rap FR, Rap US,
trap, ...) sans avoir besoin d'analyser une playlist de référence soi-même.

Chaque preset est un fichier JSON dans ce dossier avec la structure :
    {
      "key": str,
      "name": str,
      "description": str,
      "n_tracks_source": int,
      "source_playlist_name": str,
      "pattern": dict (au même format que PlaylistPattern.pattern_json)
    }

Pour ajouter un preset : extraire un pattern existant via script, le sauver
en JSON ici, redémarrer le serveur. Les presets sont lus au démarrage et au
load (pas de hot-reload, OK pour le mono-user).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

PRESETS_DIR = Path(__file__).parent
PRESET_ID_PREFIX = "preset:"


@dataclass(slots=True, frozen=True)
class ThresholdPreset:
    key: str
    name: str
    description: str
    n_tracks_source: int
    source_playlist_name: str
    pattern: dict


@lru_cache(maxsize=1)
def _load_all() -> dict[str, ThresholdPreset]:
    """Scanne tous les *.json du dossier, retourne un dict {key: preset}."""
    out: dict[str, ThresholdPreset] = {}
    for path in sorted(PRESETS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Skipping invalid preset %s: %s", path.name, e)
            continue
        key = data.get("key")
        pattern = data.get("pattern")
        if not isinstance(key, str) or not isinstance(pattern, dict):
            log.warning("Preset %s missing required fields, skip", path.name)
            continue
        out[key] = ThresholdPreset(
            key=key,
            name=data.get("name", key),
            description=data.get("description", ""),
            n_tracks_source=int(data.get("n_tracks_source", 0)),
            source_playlist_name=data.get("source_playlist_name", ""),
            pattern=pattern,
        )
    log.info("Loaded %d threshold presets: %s", len(out), list(out.keys()))
    return out


def list_presets() -> list[ThresholdPreset]:
    """Retourne tous les presets, triés par key."""
    return sorted(_load_all().values(), key=lambda p: p.key)


def get_preset(key: str) -> ThresholdPreset | None:
    """Retourne un preset par sa key (sans le préfixe `preset:`)."""
    return _load_all().get(key)


def parse_preset_id(spotify_id: str) -> str | None:
    """Extrait la key d'un ID `preset:KEY`, sinon None."""
    if spotify_id.startswith(PRESET_ID_PREFIX):
        return spotify_id[len(PRESET_ID_PREFIX):]
    return None
