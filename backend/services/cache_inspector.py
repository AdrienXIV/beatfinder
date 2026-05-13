"""Inspection et flush des caches sur disque (audio YouTube, audio local, briefs, DB).

Les fonctions retournent des dicts JSON-friendly pour exposer via API. Les
opérations destructives sont limitées à 3 catégories sûres ; la DB n'est
jamais touchée.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.domain.models import (
    Playlist,
    PlaylistPattern,
    PlaylistTrack,
    Track,
    TrackAnalysis,
)

log = logging.getLogger("backend.cache_inspector")

CacheKind = Literal["youtube", "local-audio", "reports", "actions"]
FLUSHABLE: tuple[CacheKind, ...] = ("youtube", "local-audio", "reports", "actions")


def _total_size(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        try:
            total += p.stat().st_size
        except OSError:
            continue
    return total


def _list_files(root: Path, pattern: str = "*") -> list[Path]:
    if not root.is_dir():
        return []
    return [p for p in root.glob(pattern) if p.is_file()]


def _youtube_audio_files(data_dir: Path) -> list[Path]:
    """Audio téléchargé depuis YouTube : data/audio/*.mp3 et autres formats."""
    root = data_dir / "audio"
    if not root.is_dir():
        return []
    files = []
    for ext in (".mp3", ".m4a", ".webm", ".opus", ".ogg"):
        files.extend(p for p in root.glob(f"*{ext}") if p.is_file())
    return files


def _local_audio_files(data_dir: Path) -> list[Path]:
    """Audio uploadé localement : data/audio/local/{proj_uuid}/* (récursif)."""
    root = data_dir / "audio" / "local"
    if not root.is_dir():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def _report_files(data_dir: Path) -> list[Path]:
    """Briefs markdown + CSV : data/reports/*.md et data/reports/*.csv."""
    root = data_dir / "reports"
    if not root.is_dir():
        return []
    files = [p for p in root.glob("*.md") if p.is_file()]
    files.extend(p for p in root.glob("*.csv") if p.is_file())
    return files


def _action_plan_files(data_dir: Path) -> list[Path]:
    """Plans d'action cachés : data/reports/actions/*.json."""
    root = data_dir / "reports" / "actions"
    if not root.is_dir():
        return []
    return [p for p in root.glob("*.json") if p.is_file()]


def _db_file(data_dir: Path) -> Path:
    return data_dir / "analyses.db"


def _db_counts(session: Session) -> dict[str, int]:
    return {
        "playlists": int(session.scalar(select(func.count(Playlist.id))) or 0),
        "tracks": int(session.scalar(select(func.count(Track.id))) or 0),
        "playlist_tracks": int(
            session.scalar(select(func.count()).select_from(PlaylistTrack)) or 0
        ),
        "analyses": int(session.scalar(select(func.count(TrackAnalysis.id))) or 0),
        "patterns": int(session.scalar(select(func.count(PlaylistPattern.id))) or 0),
    }


def get_cache_stats(data_dir: Path, session: Session) -> dict[str, Any]:
    """Renvoie tailles + counts par catégorie, plus stats DB."""
    yt = _youtube_audio_files(data_dir)
    local = _local_audio_files(data_dir)
    reports = _report_files(data_dir)
    actions = _action_plan_files(data_dir)
    db = _db_file(data_dir)
    db_size = db.stat().st_size if db.is_file() else 0

    return {
        "youtube": {
            "kind": "youtube",
            "label": "Audio YouTube",
            "description": "data/audio/*.mp3, *.m4a, …",
            "n_files": len(yt),
            "size_bytes": _total_size(yt),
            "flushable": True,
        },
        "local-audio": {
            "kind": "local-audio",
            "label": "Audio local (uploads)",
            "description": "data/audio/local/{project}/*",
            "n_files": len(local),
            "size_bytes": _total_size(local),
            "flushable": True,
        },
        "reports": {
            "kind": "reports",
            "label": "Briefs + CSV",
            "description": "data/reports/*.md, *.csv",
            "n_files": len(reports),
            "size_bytes": _total_size(reports),
            "flushable": True,
        },
        "actions": {
            "kind": "actions",
            "label": "Plans d'action",
            "description": "data/reports/actions/*.json",
            "n_files": len(actions),
            "size_bytes": _total_size(actions),
            "flushable": True,
        },
        "db": {
            "kind": "db",
            "label": "Base SQLite",
            "description": "data/analyses.db",
            "n_files": 1 if db_size else 0,
            "size_bytes": db_size,
            "flushable": False,
            "counts": _db_counts(session),
        },
    }


def flush_cache(kind: CacheKind, data_dir: Path) -> dict[str, Any]:
    """Supprime les fichiers de la catégorie indiquée. La DB n'est jamais flushée.

    Retourne {n_files_deleted, bytes_freed}. Pour `local-audio` on garde les
    dossiers vides : les analyses DB référencent les paths, mais comme on
    flush juste les fichiers les `audio_path` deviennent stale (à reanalyser).
    """
    if kind not in FLUSHABLE:
        raise ValueError(f"Cannot flush cache kind {kind!r}")

    if kind == "youtube":
        files = _youtube_audio_files(data_dir)
    elif kind == "local-audio":
        files = _local_audio_files(data_dir)
    elif kind == "reports":
        files = _report_files(data_dir)
    elif kind == "actions":
        files = _action_plan_files(data_dir)
    else:
        files = []

    bytes_freed = _total_size(files)
    n_deleted = 0
    for p in files:
        try:
            p.unlink()
            n_deleted += 1
        except OSError as exc:
            log.warning("Failed to delete %s: %s", p, exc)

    # Pour local-audio, on nettoie aussi les dossiers vides (data/audio/local/{uuid})
    if kind == "local-audio":
        local_root = data_dir / "audio" / "local"
        if local_root.is_dir():
            for child in local_root.iterdir():
                if child.is_dir():
                    try:
                        next(child.iterdir())
                    except StopIteration:
                        try:
                            child.rmdir()
                        except OSError:
                            pass

    log.info("Flushed %s cache: %d files, %d bytes", kind, n_deleted, bytes_freed)
    return {
        "kind": kind,
        "n_files_deleted": n_deleted,
        "bytes_freed": bytes_freed,
    }
