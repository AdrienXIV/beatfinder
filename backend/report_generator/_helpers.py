"""Constantes, helpers d'accès dict, interprétations qualitatives, ASCII bars.

Ne contient pas de logique métier — uniquement des helpers réutilisables par
les modules d'analytics, de recommandations et de rendu.
"""
from __future__ import annotations

from typing import Any, Final

DROP_HIGH_VARIANCE_IQR: Final[float] = 0.25  # IQR p75-p25 > 25 points → drop imprévisible
MIN_RELIABLE_TRACKS: Final[int] = 3  # en-dessous, la distribution filtrée n'est pas fiable

# Détection bimodale BPM : gap entre 2 modes >= 20 BPM, vallée <= 30% du pic
BPM_BIMODAL_MIN_GAP: Final[int] = 20
BPM_BIMODAL_VALLEY_RATIO: Final[float] = 0.30

# Features pondérées pour le fit_score par track (path tuple → poids)
FIT_FEATURES: Final[list[tuple[tuple[str, ...], float]]] = [
    (("tempo", "bpm"), 1.5),
    (("energy", "lufs_integrated"), 1.0),
    (("energy", "true_peak_db"), 0.5),
    (("energy", "dynamic_range_db"), 0.7),
    (("energy", "crest_factor_db"), 0.5),
    (("spectral", "band_energy", "sub"), 1.0),
    (("spectral", "band_energy", "bass"), 1.0),
    (("spectral", "band_energy", "low_mid"), 0.5),
    (("spectral", "band_energy", "mid"), 0.7),
    (("spectral", "band_energy", "high_mid"), 0.5),
    (("spectral", "band_energy", "high"), 0.5),
    (("spectral", "centroid_hz"), 0.7),
    (("structure", "drop_position_ratio"), 0.5),
]


def _walk_pattern(d: dict | None, *path: str) -> dict | None:
    """Identique à _walk_value mais retourne le sous-dict (pas la valeur)."""
    val: Any = d
    for p in path:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
        if val is None:
            return None
    return val if isinstance(val, dict) else None


def _walk_value(d: dict | None, *path: str) -> Any:
    val: Any = d
    for p in path:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
        if val is None:
            return None
    return val


# -------------------- Interprétations qualitatives --------------------

def _interpret_lufs(lufs: float) -> str:
    if lufs > -10:
        return "très chaud, limiter agressif (Spotify normalize à -14, tu pousses fort au-dessus)"
    if lufs > -13:
        return "streaming standard, légèrement au-dessus de la norm Spotify (-14)"
    if lufs > -16:
        return "streaming-friendly, moins compressé"
    if lufs > -20:
        return "calme, atypique pour rap moderne"
    return "très calme, exotique"


def _interpret_tp(tp: float) -> str:
    if tp > 0.5:
        return "inter-sample clipping franc — signature trap moderne"
    if tp > -0.5:
        return "à la limite, clipping inter-sample possible"
    return "headroom positif, master propre"


def _interpret_dr(dr: float) -> str:
    if dr < 8:
        return "très compressé, peu de respiration"
    if dr < 15:
        return "compression modérée"
    if dr < 20:
        return "dynamique large (intro calme → drop fort)"
    return "très large (breaks marqués ou intro quasi-silencieuse)"


def _interpret_onset(density: float) -> str:
    if density < 2:
        return "rythme lâche"
    if density < 4:
        return "rythme moyen"
    if density < 6:
        return "rythme dense (1/16 plein, hats actifs)"
    return "très dense (hat rolls, trap hats rapides)"


def _interpret_drop(ratio: float) -> str:
    pct = ratio * 100
    if pct < 20:
        return "drop ultra-précoce, intro très courte (optimisé skip-rate streaming)"
    if pct < 35:
        return "drop standard rap moderne"
    if pct < 50:
        return "intro plus longue, structure classique"
    return "drop tardif (atypique pour rap moderne)"


def _interpret_centroid(centroid: float) -> str:
    if centroid < 2000:
        return "très sombre"
    if centroid < 3500:
        return "sombre (typique rap/trap)"
    if centroid < 5000:
        return "équilibré"
    return "brillant"


def _interpret_flatness(f: float) -> str:
    if f < 0.005:
        return "très tonal (production léchée)"
    if f < 0.02:
        return "majoritairement tonal"
    return "présence de bruit (hats, ambiance)"


# -------------------- Helpers spectraux --------------------

def _band_bar(value: float, width: int = 20) -> str:
    """Barre ASCII proportionnelle. `▎` pour les valeurs > 0 mais < 1/width
    (évite les backticks vides dans le markdown rendu). width=20 → échelle dégressive
    qui se loge dans des cellules de tableau étroites tout en gardant la lisibilité."""
    if value <= 0:
        return "—"
    n_blocks = int(value * width)
    if n_blocks == 0:
        return "▎"
    return "█" * n_blocks


def _spectral_profile_label(bands: dict) -> str:
    low_end = bands["sub"]["median"] + bands["bass"]["median"]
    top_end = bands["high_mid"]["median"] + bands["high"]["median"]
    if low_end > 0.6:
        if top_end < 0.05:
            return "low-end dominant + tops étouffés (trap/rap moderne textbook)"
        return "low-end dominant"
    if low_end > 0.45:
        return "low-end fort mais pas écrasant"
    return "spectre plus équilibré (rare en trap)"
