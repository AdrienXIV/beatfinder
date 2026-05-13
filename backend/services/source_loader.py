"""Résolution d'un ID Spotify-like (playlist / track / preset) en pattern source.

Centralise la logique de chargement pour qu'elle soit réutilisable par les
routes actions (plan d'action 1v1) et compare/multi (radar triangulaire).

Format des IDs supportés :
- `preset:KEY`      → preset industry-standard via `threshold_presets`
- sinon             → Playlist d'abord (lookup `spotify_id`), sinon Track
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.models import Playlist, PlaylistPattern, Track, TrackAnalysis
from backend.services.pattern_extractor import build_single_track_pattern
from backend.services.threshold_presets import get_preset, parse_preset_id

SourceKind = Literal["playlist", "track", "preset"]


@dataclass(slots=True)
class PatternSource:
    """Wrap un pattern + meta pour usage uniforme (action_planner, multi_compare)."""

    id: str
    name: str
    n_tracks: int
    pattern: dict
    pattern_id: int | None  # PlaylistPattern.id si playlist, sinon None
    kind: SourceKind


def load_pattern_source(session: Session, spotify_id: str) -> PatternSource:
    """Résout un ID en source pattern.

    Lève 404 si introuvable, 409 si pas de pattern/analyse disponible.
    """
    preset_key = parse_preset_id(spotify_id)
    if preset_key is not None:
        preset = get_preset(preset_key)
        if preset is None:
            raise HTTPException(
                status_code=404,
                detail=f"Preset {preset_key!r} not found",
            )
        return PatternSource(
            id=spotify_id,
            name=preset.name,
            n_tracks=preset.n_tracks_source,
            pattern=preset.pattern,
            pattern_id=None,
            kind="preset",
        )

    p = session.scalar(select(Playlist).where(Playlist.spotify_id == spotify_id))
    if p is not None:
        pat = session.scalar(
            select(PlaylistPattern)
            .where(PlaylistPattern.playlist_id == p.id)
            .order_by(PlaylistPattern.id.desc()),
        )
        if pat is None:
            raise HTTPException(
                status_code=409,
                detail=f"Playlist {spotify_id!r} has no pattern — analyze it first",
            )
        return PatternSource(
            id=p.spotify_id,
            name=p.name,
            n_tracks=pat.n_tracks_analyzed,
            pattern=pat.pattern_json,
            pattern_id=pat.id,
            kind="playlist",
        )

    t = session.scalar(select(Track).where(Track.spotify_id == spotify_id))
    if t is None:
        raise HTTPException(
            status_code=404,
            detail=f"ID {spotify_id!r} not found (neither playlist nor track)",
        )
    analysis = session.scalar(
        select(TrackAnalysis)
        .where(TrackAnalysis.track_id == t.id)
        .order_by(TrackAnalysis.id.desc()),
    )
    if analysis is None:
        raise HTTPException(
            status_code=409,
            detail=f"Track {spotify_id!r} has no analysis — analyze it first",
        )
    display_name = f"{t.artist} — {t.title}" if t.artist else t.title
    return PatternSource(
        id=t.spotify_id,
        name=display_name,
        n_tracks=1,
        pattern=build_single_track_pattern(analysis.features_json),
        pattern_id=None,
        kind="track",
    )
