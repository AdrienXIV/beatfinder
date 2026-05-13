"""Local projects — analyse de fichiers audio uploadés sans passer par Spotify.

Re-exporte l'API publique. Split interne :
- `_audio_io.py` : I/O fichiers + metadata (extrait pour isoler des deps mutagen/FS)
- `service.py` : pipeline DB + analyse (la vraie logique métier)
"""
from __future__ import annotations

from ._audio_io import ALLOWED_EXTENSIONS, LOCAL_PLAYLIST_PREFIX
from .service import (
    AnalyzeMode,
    add_tracks,
    brief_filename,
    create_project,
    delete_project,
    is_local_playlist,
    make_local_id,
    run_local_pipeline,
)

__all__ = [
    "ALLOWED_EXTENSIONS",
    "LOCAL_PLAYLIST_PREFIX",
    "AnalyzeMode",
    "add_tracks",
    "brief_filename",
    "create_project",
    "delete_project",
    "is_local_playlist",
    "make_local_id",
    "run_local_pipeline",
]
