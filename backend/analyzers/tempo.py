"""Analyse tempo + rythme.

Features :
- BPM avec correction anti-octave-error :
    * Cross-check librosa.feature.tempo + librosa.beat.beat_track
    * Heuristique : si BPM hors [90, 180], multiplier ou diviser par 2
    * Confiance basée sur l'accord entre les 2 méthodes
- Beat consistency : 1 - std normalisée des intervalles entre beats
- Onset density : onsets par seconde
- Swing : ratio médian d'intervalles consécutifs (>1.0 = swung, ~1.0 = straight)
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Final

import librosa
import numpy as np

from ._loader import AudioBundle

logger = logging.getLogger(__name__)

OCTAVE_LOW: Final[float] = 90.0
OCTAVE_HIGH: Final[float] = 180.0
BPM_AGREEMENT_TOLERANCE: Final[float] = 10.0  # delta BPM pour confiance = 0


@dataclass(slots=True)
class TempoFeatures:
    bpm: float
    bpm_confidence: float        # 1.0 si les 2 méthodes convergent, 0.0 si delta >= 10 BPM
    beat_consistency: float      # 0..1, 1 = tempo très stable
    onset_density: float         # onsets / seconde
    swing_ratio: float | None    # None si pas assez d'onsets

    def as_dict(self) -> dict:
        return asdict(self)


def _correct_octave(bpm: float) -> float:
    """Ramène le BPM dans [90, 180] en doublant ou halvant."""
    if bpm <= 0:
        return 0.0
    while bpm < OCTAVE_LOW:
        bpm *= 2.0
    while bpm > OCTAVE_HIGH:
        bpm /= 2.0
    return bpm


def _estimate_swing(onset_times: np.ndarray) -> float | None:
    """Médian des ratios d'intervalles consécutifs.

    1.0 = straight (intervalles uniformes)
    1.5-2.0 = swing/triolets (alternance long-court)
    """
    if len(onset_times) < 8:
        return None
    intervals = np.diff(onset_times)
    if len(intervals) < 4:
        return None
    ratios = intervals[1:] / np.maximum(intervals[:-1], 1e-6)
    ratios = ratios[(ratios > 0.5) & (ratios < 3.0)]
    if len(ratios) < 4:
        return None
    return round(float(np.median(ratios)), 3)


def analyze(bundle: AudioBundle) -> TempoFeatures:
    """Calcule les features tempo/rythme."""
    sr = bundle.sr
    hop_length = bundle.hop_length
    onset_env = bundle.onset_env

    # 1. Deux estimations, anti-octave correction sur les deux
    bpm_feat_raw = librosa.feature.tempo(
        onset_envelope=onset_env, sr=sr, hop_length=hop_length, ac_size=10.0,
    )
    bpm_feat = float(np.atleast_1d(bpm_feat_raw)[0])

    bpm_beat_raw, beats = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=hop_length,
    )
    bpm_beat = float(np.atleast_1d(bpm_beat_raw)[0])

    bpm_feat_c = _correct_octave(bpm_feat)
    bpm_beat_c = _correct_octave(bpm_beat)

    # On privilégie beat_track (plus stable pour rap/trap)
    bpm = bpm_beat_c
    delta = abs(bpm_feat_c - bpm_beat_c)
    confidence = max(0.0, 1.0 - delta / BPM_AGREEMENT_TOLERANCE)

    if confidence < 0.5:
        logger.warning(
            "BPM incertain pour %s : feature.tempo=%.1f vs beat_track=%.1f (delta=%.1f)",
            bundle.path.name, bpm_feat_c, bpm_beat_c, delta,
        )

    # 2. Beat consistency
    if len(beats) > 1:
        beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=hop_length)
        intervals = np.diff(beat_times)
        mean_int = float(np.mean(intervals))
        std_int = float(np.std(intervals))
        consistency = max(0.0, 1.0 - (std_int / mean_int)) if mean_int > 0 else 0.0
    else:
        consistency = 0.0

    # 3. Onset density
    onset_times = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=hop_length, units="time",
    )
    duration = bundle.duration_sec
    onset_density = float(len(onset_times) / duration) if duration > 0 else 0.0

    # 4. Swing
    swing_ratio = _estimate_swing(np.asarray(onset_times))

    return TempoFeatures(
        bpm=round(bpm, 2),
        bpm_confidence=round(confidence, 3),
        beat_consistency=round(consistency, 3),
        onset_density=round(onset_density, 2),
        swing_ratio=swing_ratio,
    )
