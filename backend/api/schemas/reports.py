"""Schemas briefs markdown + compare playlists + multi-compare."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BriefOut(BaseModel):
    spotify_id: str
    playlist_name: str
    markdown: str
    generated_at: datetime
    cached: bool


class CompareRequest(BaseModel):
    id_a: str
    id_b: str
    pattern_a: int | None = None
    pattern_b: int | None = None


class CompareOut(BaseModel):
    id_a: str
    id_b: str
    name_a: str
    name_b: str
    n_tracks_a: int
    n_tracks_b: int
    markdown: str
    generated_at: datetime


class MultiCompareSourceOut(BaseModel):
    id: str
    name: str
    n_tracks: int
    kind: str  # playlist | track | preset


class SpectralRadarOut(BaseModel):
    labels: list[str]
    values: list[list[float]]  # [source_idx][band_idx]


class MultiStatRowOut(BaseModel):
    key: str
    label: str
    unit: str
    values: list[float | None]  # 1 valeur par source


class MultiCompareOut(BaseModel):
    sources: list[MultiCompareSourceOut]
    spectral_radar: SpectralRadarOut
    stats_table: list[MultiStatRowOut]
