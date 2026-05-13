"""I/O fichiers audio pour projets locaux : metadata, naming, lookup.

Isolé du service pour ne pas mélanger logique pipeline (DB + analyse) et
manipulation FS. À déplacer plus tard dans `backend.infrastructure/` si on
formalise la séparation domain/application/infrastructure.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Final

log = logging.getLogger("backend.local_projects.audio_io")

LOCAL_PLAYLIST_PREFIX: Final[str] = "local:"
ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aiff"},
)


def _safe_filename(name: str) -> str:
    base = os.path.basename(name)
    safe = re.sub(r"[^A-Za-z0-9._\-\s]", "_", base)
    return (safe[:200] or "unnamed").strip()


def _parse_filename(stem: str) -> tuple[str | None, str]:
    """Parse 'Artist - Title' depuis un nom de fichier. Tente plusieurs séparateurs.

    Retourne (artist, title). artist = None si pas de séparateur trouvé.
    """
    for sep in (" — ", " – ", " - ", " _ "):
        if sep in stem:
            artist_part, _, title_part = stem.partition(sep)
            artist = artist_part.strip()
            title = title_part.strip()
            if artist and title:
                return artist, title
    return None, stem


def _read_metadata(audio_path: Path) -> dict[str, Any]:
    """Lit les tags ID3/audio. Fallback : parse `Artist - Title` du filename."""
    fallback_artist, fallback_title = _parse_filename(audio_path.stem)
    title = fallback_title
    artist = fallback_artist or ""
    duration_ms = 0
    try:
        from mutagen import File as MutagenFile

        f = MutagenFile(audio_path)
        if f is not None:
            tags = getattr(f, "tags", None) or {}

            def _first(*keys: str) -> str | None:
                for k in keys:
                    if k in tags:
                        v = tags[k]
                        if isinstance(v, list) and v:
                            return str(v[0])
                        return str(v)
                return None

            t = _first("TIT2", "title", "\xa9nam")
            if t and t.strip():
                title = t.strip()
            a = _first("TPE1", "artist", "\xa9ART")
            if a and a.strip():
                artist = a.strip()
            if hasattr(f, "info") and hasattr(f.info, "length"):
                duration_ms = int(f.info.length * 1000)
    except Exception:  # noqa: BLE001
        log.warning("Failed to read metadata from %s", audio_path, exc_info=True)
    return {"title": title, "artist": artist, "duration_ms": duration_ms}


def _find_audio_path(
    track_spotify_id: str, project_spotify_id: str, data_dir: Path,
) -> Path | None:
    """Cherche le fichier audio par hash dans le dossier du project."""
    proj_uuid = project_spotify_id[len(LOCAL_PLAYLIST_PREFIX):]
    parts = track_spotify_id.rsplit(":", 1)
    if len(parts) < 2:
        return None
    file_hash = parts[-1]
    local_dir = data_dir / "audio" / "local" / proj_uuid
    if not local_dir.is_dir():
        return None
    matches = list(local_dir.glob(f"{file_hash}_*"))
    return matches[0] if matches else None
