"""Schemas plan d'action (killer feature)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActionItemOut(BaseModel):
    key: str
    category: str
    metric: str
    priority: str
    current: float | None = None
    target: float | None = None
    delta: float | None = None
    unit: str
    action: str
    rationale: str


class ActionPlanOut(BaseModel):
    from_id: str
    from_name: str
    from_n_tracks: int
    to_id: str
    to_name: str
    to_n_tracks: int
    from_pattern_id: int | None = None
    to_pattern_id: int | None = None
    # Médianes par bande spectrale (ratio 0-1) pour les graphiques radar
    from_bands: dict[str, float] = {}
    to_bands: dict[str, float] = {}
    items: list[ActionItemOut]
    generated_at: datetime
    cached: bool


class ComparedTargetOut(BaseModel):
    target_id: str
    target_name: str
    target_n_tracks: int
    n_items: int
    generated_at: datetime


class ComparedSourceOut(BaseModel):
    """Source d'un plan d'action déjà généré (pour les pastilles 'déjà comparé')."""

    from_id: str
    n_targets: int


class ThresholdPresetOut(BaseModel):
    """Preset de pattern industry-standard (Rap FR, US, ...) utilisable comme cible."""

    key: str
    target_id: str
    name: str
    description: str
    n_tracks_source: int
    source_playlist_name: str


class StylePredictionItemOut(BaseModel):
    """Une prédiction de style avec sa probabilité."""

    style: str
    probability: float


class StylePredictionOut(BaseModel):
    """Sortie du classifier de style pour un pattern donné."""

    source_id: str
    source_name: str
    predictions: list[StylePredictionItemOut]
    model_classes: list[str]
    model_cv_accuracy: float
