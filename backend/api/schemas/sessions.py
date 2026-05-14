"""Schemas pour les sessions créatives (CreativeSession + SessionVersion)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .playlists import TrackOut

TargetKind = Literal["spotify_playlist", "spotify_track", "upload", "local_playlist"]


class CreateSessionIn(BaseModel):
    """Body de POST /sessions.

    Phase 1 : source = URL Spotify (playlist ou track) déjà analysée.
    Phase 2 ouvrira aux uploads et aux playlists Beatfinder existantes.
    """

    source_url: str  # URL ou ID Spotify d'une playlist/track déjà en DB
    ambiance: dict[str, str] | None = None


class SessionVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_number: int
    name: str
    fit_score: float | None = None
    created_at: datetime


class CreativeSessionSummaryOut(BaseModel):
    """Listing dashboard."""

    model_config = ConfigDict(from_attributes=True)

    spotify_id: str
    name: str
    target_kind: TargetKind
    target_name: str
    n_versions: int
    last_fit_score: float | None = None
    is_locked: bool = False
    created_at: datetime
    updated_at: datetime


class CreativeSessionDetailOut(BaseModel):
    """Détail complet pour /sessions/[id]."""

    spotify_id: str
    name: str
    target_kind: TargetKind
    target_ref: str
    target_name: str
    target_pattern: dict
    # Quand target_kind='spotify_track' : meta + features de la track cible
    # avec overrides appliqués + indicateur de confiance + alternatives BPM.
    target_track: TrackOut | None = None
    # Quand target_kind ∈ ('spotify_playlist', 'local_playlist') : listing
    # complet des tracks de la playlist cible pour la review en mode draft.
    target_tracks: list[TrackOut] | None = None
    ambiance: dict[str, str] | None = None
    plan_md: str
    versions: list[SessionVersionOut]
    is_locked: bool = False
    locked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
