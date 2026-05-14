"""Schemas playlists, tracks, patterns."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PlaylistSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    spotify_id: str
    name: str
    owner_display_name: str | None = None
    description: str | None = None
    n_tracks: int = 0
    n_patterns: int = 0
    last_analyzed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    spotify_id: str
    title: str
    artist: str
    duration_ms: int
    release_date: str | None = None
    position: int = 0
    has_analysis: bool = False
    audio_path: str | None = None
    # Features synthétiques pour l'affichage tabulaire — extraites de la dernière
    # analyse si présente. None si has_analysis=False.
    bpm: float | None = None
    key_note: str | None = None      # ex: "A", "C#"
    key_mode: str | None = None      # "major" / "minor"
    key_uncertain: bool | None = None  # True si vote 1/3 sans majorité
    # Override / fiabilité de l'analyse (pour UI ⚠ + bouton "Corriger").
    is_overridden: bool = False     # True si BPM/key viennent d'une correction manuelle
    confidence_low: bool = False    # True si au moins 1 raison de doute (cf. confidence_reasons)
    confidence_reasons: list[str] = []  # raisons textuelles à afficher en tooltip
    bpm_alt_hypotheses: list[float] = []  # alternatives plausibles (×2, /2, ×1.5, /1.5)


class PatternSummaryOut(BaseModel):
    id: int
    n_tracks_analyzed: int
    analyzer_version: str
    created_at: datetime
    # Médianes principales pour l'évolution temporelle (tab Patterns)
    bpm_median: float | None = None
    lufs_median: float | None = None
    sub_median: float | None = None
    bass_median: float | None = None
    minor_ratio: float | None = None


class PlaylistDetailOut(BaseModel):
    spotify_id: str
    name: str
    owner_display_name: str | None = None
    description: str | None = None
    tracks: list[TrackOut]
    patterns: list[PatternSummaryOut]
    latest_pattern: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class PatternOut(BaseModel):
    id: int
    playlist_spotify_id: str
    n_tracks_analyzed: int
    analyzer_version: str
    pattern: dict[str, Any]
    created_at: datetime


class TrackAnalysisOut(BaseModel):
    spotify_id: str
    title: str
    artist: str
    duration_ms: int
    release_date: str | None = None
    audio_path: str | None = None
    analyzer_version: str
    features: dict[str, Any]
    analyzed_at: datetime
