"""Segmentation structurelle.

Features :
- duration_sec : durée totale
- n_sections : nombre de sections distinctes (segmentation agglomérative MFCC)
- drop_position_sec / _ratio : timing du drop principal (heuristique = pic de
  gradient sur le RMS de la composante percussive, dans la 1ère moitié, hors
  les 5% du début pour éviter l'attaque)
- section_boundaries_sec : timestamps des starts de section
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import librosa
import numpy as np

from ._loader import AudioBundle

SMOOTH_WINDOW = 8


@dataclass(slots=True)
class StructureFeatures:
    duration_sec: float
    n_sections: int
    drop_position_sec: float
    drop_position_ratio: float
    section_boundaries_sec: list[float]

    def as_dict(self) -> dict:
        return asdict(self)


def _drop_position(bundle: AudioBundle) -> tuple[float, float]:
    """Retourne (sec, ratio_durée) du drop principal."""
    rms_perc = librosa.feature.rms(
        y=bundle.y_percussive, hop_length=bundle.hop_length,
    )[0]
    duration = bundle.duration_sec
    if len(rms_perc) < SMOOTH_WINDOW * 2 or duration <= 0:
        return (0.0, 0.0)

    smooth = np.convolve(
        rms_perc, np.ones(SMOOTH_WINDOW) / SMOOTH_WINDOW, mode="same",
    )
    grad = np.gradient(smooth)
    half = len(grad) // 2
    skip = max(1, len(grad) // 20)
    if half <= skip:
        return (0.0, 0.0)

    drop_idx = int(np.argmax(grad[skip:half])) + skip
    drop_time = float(librosa.frames_to_time(
        drop_idx, sr=bundle.sr, hop_length=bundle.hop_length,
    ))
    return (round(drop_time, 2), round(drop_time / duration, 3))


def analyze(bundle: AudioBundle) -> StructureFeatures:
    y, sr = bundle.y, bundle.sr
    hop = bundle.hop_length
    duration = bundle.duration_sec

    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop, n_mfcc=13)

    # Cible le nombre de sections en fonction de la durée :
    # ~1 section toutes les 30s, borné entre 3 et 10
    target = max(3, min(10, int(round(duration / 30.0))))
    # Garde-fou : au moins 4 frames par cluster
    n_clusters = min(target, max(2, mfcc.shape[1] // 4))
    if n_clusters < 2:
        n_clusters = 2

    boundaries_frames = librosa.segment.agglomerative(mfcc, k=n_clusters)
    boundary_times = librosa.frames_to_time(
        boundaries_frames, sr=sr, hop_length=hop,
    )

    drop_sec, drop_ratio = _drop_position(bundle)

    return StructureFeatures(
        duration_sec=round(duration, 2),
        n_sections=int(len(boundaries_frames)),
        drop_position_sec=drop_sec,
        drop_position_ratio=drop_ratio,
        section_boundaries_sec=[round(float(t), 2) for t in boundary_times],
    )
