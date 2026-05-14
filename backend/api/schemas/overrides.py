"""Schemas pour la correction manuelle de BPM / tonalité d'une track."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

KeyNote = Literal[
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
]
KeyMode = Literal["major", "minor"]


class TrackOverrideIn(BaseModel):
    """Body de PATCH /tracks/{spotify_id}/overrides.

    Tous les champs sont optionnels — seuls les fournis sont mis à jour
    (partial update). Passer `null` explicitement reset le champ.
    """

    bpm: float | None = Field(default=None, ge=20, le=300)
    key_note: KeyNote | None = None
    key_mode: KeyMode | None = None


class TrackOverrideOut(BaseModel):
    bpm: float | None = None
    key_note: str | None = None
    key_mode: str | None = None
