"""Analyse énergie + dynamique.

Features :
- RMS moyen + std (linéaire)
- LUFS intégré (pyloudnorm, norme broadcast EBU R128)
- True Peak max en dBFS (oversampling 4x linéaire, approximation ITU-R BS.1770)
- Crest factor en dB (Peak / RMS)
- Plage dynamique en dB (p95 - p10 du RMS, simpli vs TT Dynamic Range Meter)
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import numpy as np
import pyloudnorm as pyln

from ._loader import AudioBundle

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EnergyFeatures:
    rms_mean: float
    rms_std: float
    lufs_integrated: float | None    # None si signal silencieux ou trop court
    true_peak_db: float | None       # None si silence total
    crest_factor_db: float
    dynamic_range_db: float

    def as_dict(self) -> dict:
        return asdict(self)


def _crest_factor_db(y: np.ndarray, rms_mean: float) -> float:
    if rms_mean <= 0:
        return 0.0
    peak = float(np.max(np.abs(y)))
    if peak <= 0:
        return 0.0
    return 20.0 * float(np.log10(peak / rms_mean))


def _dynamic_range_db(rms_frames: np.ndarray) -> float:
    """Approximation DR : p95 - p10 du RMS en dB.

    Capture l'écart entre les passages forts (mais pas les pics isolés) et les
    passages calmes (mais pas le silence absolu). Ordre de grandeur : 5-8 dB
    pour du rap/trap masterisé pour le streaming, 10-15 dB pour de la musique
    moins compressée.
    """
    if len(rms_frames) < 10:
        return 0.0
    rms_db = 20.0 * np.log10(np.maximum(rms_frames, 1e-9))
    p95 = float(np.percentile(rms_db, 95))
    p10 = float(np.percentile(rms_db, 10))
    return p95 - p10


def _true_peak_db(y: np.ndarray) -> float | None:
    """Estimation True Peak via oversampling 4x linéaire.

    Approximation simple du filtre interpolant ITU-R BS.1770.4. Suffisant pour
    estimer si un master est inter-sample-clipping (TP > 0 dBFS).
    """
    if len(y) < 4:
        return None
    y_up = np.interp(
        np.linspace(0, len(y) - 1, len(y) * 4),
        np.arange(len(y)),
        y,
    )
    peak = float(np.max(np.abs(y_up)))
    if peak <= 0:
        return None
    return 20.0 * float(np.log10(peak))


def analyze(bundle: AudioBundle) -> EnergyFeatures:
    y = bundle.y
    sr = bundle.sr
    rms = bundle.rms

    rms_mean = float(np.mean(rms))
    rms_std = float(np.std(rms))

    # LUFS integrated — pyloudnorm requiert >= 0.4s d'audio
    lufs: float | None = None
    if bundle.duration_sec >= 0.4:
        try:
            meter = pyln.Meter(sr)
            lufs_value = float(meter.integrated_loudness(y.astype(np.float64)))
            lufs = lufs_value if np.isfinite(lufs_value) else None
        except (ValueError, FloatingPointError) as exc:
            logger.warning("LUFS échec pour %s : %s", bundle.path.name, exc)
            lufs = None

    tp = _true_peak_db(y)
    crest = _crest_factor_db(y, rms_mean)
    dr = _dynamic_range_db(rms)

    return EnergyFeatures(
        rms_mean=round(rms_mean, 5),
        rms_std=round(rms_std, 5),
        lufs_integrated=round(lufs, 2) if lufs is not None else None,
        true_peak_db=round(tp, 2) if tp is not None else None,
        crest_factor_db=round(crest, 2),
        dynamic_range_db=round(dr, 2),
    )
