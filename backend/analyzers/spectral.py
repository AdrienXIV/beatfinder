"""Analyse spectrale.

Features :
- Spectral centroid moyen (Hz, "centre de masse" du spectre)
- Spectral rolloff 85% moyen (Hz, fréquence sous laquelle se trouve 85% de l'énergie)
- Spectral flatness (0..1, 0 = très tonal, 1 = bruit blanc)
- Énergie normalisée par bande critique (sub/bass/low_mid/mid/high_mid/high)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import librosa
import numpy as np

from ._loader import AudioBundle

# (nom, low_hz inclusif, high_hz exclusif)
CRITICAL_BANDS: tuple[tuple[str, float, float], ...] = (
    ("sub",      20.0,    60.0),
    ("bass",     60.0,   250.0),
    ("low_mid", 250.0,   500.0),
    ("mid",     500.0,  2000.0),
    ("high_mid", 2000.0, 6000.0),
    ("high",    6000.0, 20000.0),
)

N_FFT = 2048


@dataclass(slots=True)
class SpectralFeatures:
    centroid_hz: float
    rolloff85_hz: float
    flatness: float
    band_energy: dict[str, float]    # ratio normalisé, somme ≈ 1.0

    def as_dict(self) -> dict:
        return asdict(self)


def _band_energy_ratios(y: np.ndarray, sr: int, hop_length: int) -> dict[str, float]:
    S = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=hop_length))  # (1+N_FFT/2, n_frames)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    power = S ** 2

    band_e: dict[str, float] = {}
    total = 0.0
    for name, low, high in CRITICAL_BANDS:
        mask = (freqs >= low) & (freqs < high)
        if not np.any(mask):
            band_e[name] = 0.0
            continue
        e = float(power[mask, :].sum())
        band_e[name] = e
        total += e

    if total <= 0:
        return {name: 0.0 for name, _, _ in CRITICAL_BANDS}
    return {name: round(e / total, 4) for name, e in band_e.items()}


def analyze(bundle: AudioBundle) -> SpectralFeatures:
    y, sr = bundle.y, bundle.sr
    hop = bundle.hop_length

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
    rolloff = librosa.feature.spectral_rolloff(
        y=y, sr=sr, hop_length=hop, roll_percent=0.85,
    )[0]
    flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop)[0]

    return SpectralFeatures(
        centroid_hz=round(float(np.mean(centroid)), 2),
        rolloff85_hz=round(float(np.mean(rolloff)), 2),
        flatness=round(float(np.mean(flatness)), 4),
        band_energy=_band_energy_ratios(y, sr, hop),
    )
