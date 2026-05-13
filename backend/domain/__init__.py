"""Modèles métier persistés (SQLAlchemy ORM).

Re-exporte les entités pour préserver les imports historiques
`from backend.models import Playlist, ...` mais via le nouveau path
`from backend.domain.models import ...`.
"""
from __future__ import annotations

from .models import (
    Base,
    Playlist,
    PlaylistPattern,
    PlaylistTrack,
    Track,
    TrackAnalysis,
)

__all__ = [
    "Base",
    "Playlist",
    "PlaylistPattern",
    "PlaylistTrack",
    "Track",
    "TrackAnalysis",
]
