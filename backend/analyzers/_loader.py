"""Chargement audio + caches partagés entre analyzers.

Évite de relire 3 fois le même MP3 quand tempo / tonality / energy passent
sur le même fichier. HPSS et RMS aussi cachés en lazy.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import librosa
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_HOP_LENGTH: Final[int] = 512


class AudioBundle:
    """Audio chargé + caches lazy pour les analyzers.

    Attributes:
        path: Chemin source.
        y: Mono float32, sample rate natif (typiquement 48000 sortie yt-dlp MP3).
        sr: Sample rate natif (Hz).
        hop_length: Hop utilisé pour onset / RMS / chroma (512 par défaut).
    """

    def __init__(
        self,
        path: Path,
        y: np.ndarray,
        sr: int,
        hop_length: int = DEFAULT_HOP_LENGTH,
    ) -> None:
        self.path = path
        self.y = y
        self.sr = sr
        self.hop_length = hop_length
        self._rms: np.ndarray | None = None
        self._onset_env: np.ndarray | None = None
        self._y_harmonic: np.ndarray | None = None
        self._y_percussive: np.ndarray | None = None

    @property
    def duration_sec(self) -> float:
        return float(len(self.y) / self.sr) if self.sr > 0 else 0.0

    @property
    def rms(self) -> np.ndarray:
        if self._rms is None:
            self._rms = librosa.feature.rms(y=self.y, hop_length=self.hop_length)[0]
        return self._rms

    @property
    def onset_env(self) -> np.ndarray:
        if self._onset_env is None:
            self._onset_env = librosa.onset.onset_strength(
                y=self.y, sr=self.sr, hop_length=self.hop_length
            )
        return self._onset_env

    def _ensure_hpss(self) -> None:
        if self._y_harmonic is None or self._y_percussive is None:
            harm, perc = librosa.effects.hpss(self.y, margin=3.0)
            self._y_harmonic = harm
            self._y_percussive = perc

    @property
    def y_harmonic(self) -> np.ndarray:
        self._ensure_hpss()
        assert self._y_harmonic is not None
        return self._y_harmonic

    @property
    def y_percussive(self) -> np.ndarray:
        self._ensure_hpss()
        assert self._y_percussive is not None
        return self._y_percussive


def load_audio(
    path: Path | str,
    *,
    hop_length: int = DEFAULT_HOP_LENGTH,
) -> AudioBundle:
    """Charge un MP3 en mono à son sample rate natif (sr=None pour pyloudnorm)."""
    p = Path(path)
    y, sr = librosa.load(str(p), sr=None, mono=True)
    logger.debug("Chargé %s : %.1fs @ %dHz", p.name, len(y) / sr, sr)
    return AudioBundle(path=p, y=y, sr=int(sr), hop_length=hop_length)
