"""Analyse timbrale (MFCC).

13 coefficients MFCC, moyennes et écarts-types calculés sur tout le morceau.
Utilisé pour caractériser la "couleur" timbrale et comparer des tracks entre elles
(distance euclidienne ou cosinus dans l'espace MFCC).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import librosa
import numpy as np

from ._loader import AudioBundle

N_MFCC = 13


@dataclass(slots=True)
class TimbreFeatures:
    mfcc_mean: list[float]
    mfcc_std: list[float]

    def as_dict(self) -> dict:
        return asdict(self)


def analyze(bundle: AudioBundle) -> TimbreFeatures:
    mfcc = librosa.feature.mfcc(
        y=bundle.y, sr=bundle.sr, hop_length=bundle.hop_length, n_mfcc=N_MFCC,
    )
    return TimbreFeatures(
        mfcc_mean=[round(float(x), 3) for x in np.mean(mfcc, axis=1)],
        mfcc_std=[round(float(x), 3) for x in np.std(mfcc, axis=1)],
    )
