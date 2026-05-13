"""Comparaison N-way de patterns (radar triangulaire et au-delà).

Prend N sources hétérogènes (playlists / tracks / presets) et construit :
- un radar des 6 bandes spectrales (toujours en %, échelle commune)
- un tableau de stats clés par axe (BPM, LUFS, crest, mode, centroid, etc.)

Utilisé par `GET /api/compare/multi?ids=A,B,C[,D,E]`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.services.source_loader import PatternSource


def _walk(d: dict | None, *path: str) -> Any:
    val: Any = d
    for p in path:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
        if val is None:
            return None
    return val


def _pct(v: float | None) -> float | None:
    """Normalise une fraction 0-1 en pourcentage 0-100."""
    return round(v * 100.0, 2) if isinstance(v, (int, float)) else None


def _round(v: float | None, digits: int = 1) -> float | None:
    return round(v, digits) if isinstance(v, (int, float)) else None


# Spec des stats du tableau : key, label, unit, getter
# Le getter retourne la valeur déjà formatée (None si absent).
_STAT_SPECS: list[tuple[str, str, str, Any]] = [
    ("bpm", "BPM médian", "BPM", lambda p: _round(_walk(p, "tempo", "bpm", "median"))),
    ("bpm_std", "BPM std", "BPM", lambda p: _round(_walk(p, "tempo", "bpm", "std"))),
    ("lufs", "LUFS intégré", "dB", lambda p: _round(_walk(p, "energy", "lufs_integrated", "median"))),
    ("crest", "Crest factor", "dB", lambda p: _round(_walk(p, "energy", "crest_factor_db", "median"))),
    ("dr", "DR (p95-p10)", "dB", lambda p: _round(_walk(p, "energy", "dynamic_range_db", "median"))),
    ("true_peak", "True peak", "dBFS", lambda p: _round(_walk(p, "energy", "true_peak_db", "median"))),
    ("centroid", "Centroid spectral", "Hz", lambda p: _round(_walk(p, "spectral", "centroid_hz", "median"), 0)),
    ("rolloff", "Rolloff 85%", "Hz", lambda p: _round(_walk(p, "spectral", "rolloff85_hz", "median"), 0)),
    ("mode_minor", "Mode minor", "%", lambda p: _pct((_walk(p, "tonality", "mode", "distribution") or {}).get("minor"))),
    ("drop_pos", "Drop position", "%", lambda p: _pct(_walk(p, "structure", "drop_position_ratio", "median"))),
    ("n_sections", "Sections par track", "", lambda p: _round(_walk(p, "structure", "n_sections", "median"))),
    ("duration", "Durée moyenne", "sec", lambda p: _round(_walk(p, "duration_sec", "median"))),
]

_SPECTRAL_BANDS = (
    ("sub", "Sub 20-60Hz"),
    ("bass", "Bass 60-250Hz"),
    ("low_mid", "Low-mid 250-500Hz"),
    ("mid", "Mid 500-2kHz"),
    ("high_mid", "High-mid 2-6kHz"),
    ("high", "High 6-20kHz"),
)


@dataclass(slots=True)
class MultiCompare:
    """Résultat structuré de la comparaison N-way."""

    sources: list[dict]
    spectral_radar: dict
    stats_table: list[dict]


def build_multi_compare(sources: list[PatternSource]) -> MultiCompare:
    """Agrège N sources en un radar spectral + table stats par axe."""
    src_meta = [
        {"id": s.id, "name": s.name, "n_tracks": s.n_tracks, "kind": s.kind}
        for s in sources
    ]

    radar_values = [
        [_pct(_walk(s.pattern, "spectral", "band_energy", band, "median")) or 0.0 for band, _ in _SPECTRAL_BANDS]
        for s in sources
    ]
    spectral_radar = {
        "labels": [label for _, label in _SPECTRAL_BANDS],
        "values": radar_values,
    }

    stats_table = [
        {
            "key": key,
            "label": label,
            "unit": unit,
            "values": [getter(s.pattern) for s in sources],
        }
        for key, label, unit, getter in _STAT_SPECS
    ]

    return MultiCompare(
        sources=src_meta,
        spectral_radar=spectral_radar,
        stats_table=stats_table,
    )
