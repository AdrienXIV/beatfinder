"""Analyse tonale — consensus KS (Krumhansl-Schmuckler) + madmom CNN.

Stratégie :
- KS sur chroma_cens, high-pass 80 Hz pour virer le sub-bass qui parasite la chroma.
- madmom.features.key.CNNKeyRecognitionProcessor : modèle CNN trained sur GiantSteps.
- Consensus :
    * Si les deux méthodes sont d'accord sur la note racine → confident, on garde leur clé "majoritaire" (priorité madmom car mode mieux estimé).
    * Sinon → uncertain, on remonte les 2 candidats pour permettre une revue manuelle.

Note : sur trap français avec 808/autotune, aucune des deux méthodes ne dépasse
~60-70% d'accuracy root. Le flag uncertain est l'attitude raisonnable.
"""
from __future__ import annotations

import logging
import warnings
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache

import librosa
import numpy as np
from scipy.signal import butter, filtfilt

from ._loader import AudioBundle

logger = logging.getLogger(__name__)

NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
# Profils Krumhansl-Schmuckler (1990)
MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

SEGMENT_DURATION_SEC = 10.0
HIGHPASS_CUTOFF_HZ = 80.0
HIGHPASS_ORDER = 4


@dataclass(slots=True)
class TonalityFeatures:
    key: str                        # consensus majority vote sur 3 voters
    note: str
    mode: str
    is_uncertain: bool              # True si pas de majorité 2/3 sur la note racine
    ks_cens_key: str                # KS sur chroma_cens (+ highpass + RMS weighting)
    ks_cqt_key: str                 # KS sur chroma_cqt (+ highpass + RMS weighting)
    madmom_key: str                 # CNN GiantSteps
    vote_count: int                 # 1, 2 ou 3 — nb de méthodes d'accord sur la note racine choisie
    methods_agree_all: bool         # True si les 3 sont parfaitement d'accord (note + mode)
    ks_cens_confidence: float
    ks_cqt_confidence: float
    madmom_confidence: float
    major_minor_ratio: float
    most_common_root: str
    n_segments: int
    n_modulations: int

    def as_dict(self) -> dict:
        return asdict(self)


# -------------------- KS path --------------------

def _highpass(y: np.ndarray, sr: int) -> np.ndarray:
    """Butterworth high-pass à 80 Hz, vire le sub-bass 808."""
    nyq = sr * 0.5
    norm = HIGHPASS_CUTOFF_HZ / nyq
    b, a = butter(HIGHPASS_ORDER, norm, btype="highpass")
    return filtfilt(b, a, y).astype(np.float32)


def _rms_weighted_chroma_mean(chroma: np.ndarray, rms: np.ndarray) -> np.ndarray:
    """Moyenne du chroma pondérée par le RMS de chaque frame (skip silence)."""
    n_frames = min(chroma.shape[1], rms.shape[0])
    if n_frames == 0:
        return np.zeros(12, dtype=np.float64)
    chroma = chroma[:, :n_frames]
    rms = rms[:n_frames]
    total = float(rms.sum())
    if total <= 0:
        return chroma.mean(axis=1)
    return (chroma * (rms / total)[np.newaxis, :]).sum(axis=1)


def _ks_from_chroma(chroma_mean: np.ndarray) -> tuple[str, str, float]:
    """Renvoie (note, mode, confidence) où confidence = delta best/2nd corrélation."""
    correlations: list[tuple[float, int, str]] = []
    for i in range(12):
        for profile, mode in ((MAJOR_PROFILE, "major"), (MINOR_PROFILE, "minor")):
            shifted = np.roll(profile, i)
            denom = float(np.std(chroma_mean) * np.std(shifted))
            if denom <= 0:
                corr = 0.0
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    corr = float(np.corrcoef(chroma_mean, shifted)[0, 1])
                if not np.isfinite(corr):
                    corr = 0.0
            correlations.append((corr, i, mode))
    correlations.sort(key=lambda x: -x[0])
    best = correlations[0]
    second = correlations[1]
    delta = float(best[0] - second[0])
    return NOTES[best[1]], best[2], delta


def _ks_analyze(
    bundle: AudioBundle,
    chroma_fn,
    *,
    with_segments: bool = False,
) -> tuple[str, str, float, list[tuple[str, str]]]:
    """Run KS sur le morceau entier avec la chroma fonction passée en paramètre.

    Si with_segments=True, retourne aussi la liste des (note, mode) par segment
    de 10s pour estimer les modulations.
    """
    sr = bundle.sr
    hop = bundle.hop_length
    y_hp = _highpass(bundle.y_harmonic, sr)
    tuning = librosa.estimate_tuning(y=y_hp, sr=sr)
    chroma = chroma_fn(y=y_hp, sr=sr, tuning=tuning, hop_length=hop)
    rms = bundle.rms

    global_mean = _rms_weighted_chroma_mean(chroma, rms)
    g_note, g_mode, g_conf = _ks_from_chroma(global_mean)

    segments: list[tuple[str, str]] = []
    if with_segments:
        frames_per_seg = int(librosa.time_to_frames(
            SEGMENT_DURATION_SEC, sr=sr, hop_length=hop,
        ))
        n_frames = chroma.shape[1]
        for start in range(0, n_frames, frames_per_seg):
            end = min(start + frames_per_seg, n_frames)
            if end - start < frames_per_seg // 2:
                break
            seg_chroma = chroma[:, start:end]
            seg_rms = rms[start:end]
            seg_mean = _rms_weighted_chroma_mean(seg_chroma, seg_rms)
            n, m, _ = _ks_from_chroma(seg_mean)
            segments.append((n, m))

    return g_note, g_mode, g_conf, segments


# -------------------- madmom path --------------------

@lru_cache(maxsize=1)
def _madmom_processor():
    """Cache le CNN processor (loading des poids = ~1s, à faire une seule fois)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from madmom.features.key import CNNKeyRecognitionProcessor
        return CNNKeyRecognitionProcessor()


def _madmom_analyze(audio_path: str) -> tuple[str, str, float]:
    """Run madmom CNN sur le fichier audio (path direct, madmom le re-décode)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from madmom.features.key import key_prediction_to_label
        proc = _madmom_processor()
        pred = proc(audio_path)  # shape (1, 24) ou (24,)
        flat = np.asarray(pred).ravel()
        # 24 classes : 0-11 = majors C..B, 12-23 = minors C..B
        idx = int(np.argmax(flat))
        confidence = float(flat[idx])
        label = key_prediction_to_label(pred)  # ex. "C minor"
        # Normalise "C major" / "C minor" -> note + mode
        parts = label.split()
        note = parts[0].replace("b", "#") if "b" in parts[0].lower() else parts[0]
        # Mapping flat→sharp pour cohérence avec KS (qui ne sort que des dièses)
        flat_to_sharp = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
        note = flat_to_sharp.get(parts[0], parts[0])
        mode = parts[1].lower() if len(parts) > 1 else "major"
        return note, mode, confidence


# -------------------- Consensus --------------------

def analyze(bundle: AudioBundle) -> TonalityFeatures:
    # Voter 1 : KS sur chroma_cens (+ segments pour les modulations)
    cens_note, cens_mode, cens_conf, segments = _ks_analyze(
        bundle, librosa.feature.chroma_cens, with_segments=True,
    )

    # Voter 2 : KS sur chroma_cqt (responsivité différente de cens, errors moins corrélées)
    cqt_note, cqt_mode, cqt_conf, _ = _ks_analyze(
        bundle, librosa.feature.chroma_cqt, with_segments=False,
    )

    # Voter 3 : madmom CNN
    try:
        mm_note, mm_mode, mm_conf = _madmom_analyze(str(bundle.path))
    except Exception as exc:  # noqa: BLE001 — madmom peut throw varié
        logger.warning("madmom a échoué sur %s : %s", bundle.path.name, exc)
        mm_note, mm_mode, mm_conf = cens_note, cens_mode, 0.0

    # Majority vote sur la note racine
    voters = [
        ("ks_cens", cens_note, cens_mode),
        ("ks_cqt", cqt_note, cqt_mode),
        ("madmom", mm_note, mm_mode),
    ]
    note_counts = Counter(n for _, n, _ in voters)
    top_note, top_count = note_counts.most_common(1)[0]

    if top_count >= 2:
        # Majorité root : on prend la note la plus fréquente.
        # Mode : priorité à madmom (CNN, moins biaisé "major" que les profils KS)
        # quand madmom a voté pour cette racine. Sinon, majority KS.
        chosen_note = top_note
        voters_with_root = [(name, m) for name, n, m in voters if n == top_note]
        madmom_mode = next(
            (m for name, m in voters_with_root if name == "madmom"), None,
        )
        if madmom_mode is not None:
            chosen_mode = madmom_mode
        else:
            chosen_mode = Counter(
                m for _, m in voters_with_root
            ).most_common(1)[0][0]
        vote_count = top_count
        is_uncertain = False
    else:
        # Aucune majorité (3 réponses différentes) → fallback madmom + flag uncertain
        chosen_note = mm_note
        chosen_mode = mm_mode
        vote_count = 1
        is_uncertain = True
        logger.warning(
            "Tonalité incertaine pour %s : KS-cens=%s%s / KS-cqt=%s%s / madmom=%s%s — aucune majorité",
            bundle.path.name,
            cens_note, cens_mode[0],
            cqt_note, cqt_mode[0],
            mm_note, mm_mode[0],
        )

    methods_agree_all = (
        cens_note == cqt_note == mm_note
        and cens_mode == cqt_mode == mm_mode
    )

    # Stats sur les segments (chroma_cens)
    if segments:
        major_count = sum(1 for _, m in segments if m == "major")
        major_minor_ratio = major_count / len(segments)
        most_common_root = Counter(n for n, _ in segments).most_common(1)[0][0]
        n_modulations = sum(
            1 for a, b in zip(segments, segments[1:]) if a != b
        )
    else:
        major_minor_ratio = 1.0 if chosen_mode == "major" else 0.0
        most_common_root = chosen_note
        n_modulations = 0

    return TonalityFeatures(
        key=f"{chosen_note} {chosen_mode.title()}",
        note=chosen_note,
        mode=chosen_mode,
        is_uncertain=is_uncertain,
        ks_cens_key=f"{cens_note} {cens_mode.title()}",
        ks_cqt_key=f"{cqt_note} {cqt_mode.title()}",
        madmom_key=f"{mm_note} {mm_mode.title()}",
        vote_count=vote_count,
        methods_agree_all=methods_agree_all,
        ks_cens_confidence=round(cens_conf, 3),
        ks_cqt_confidence=round(cqt_conf, 3),
        madmom_confidence=round(mm_conf, 3),
        major_minor_ratio=round(major_minor_ratio, 3),
        most_common_root=most_common_root,
        n_segments=len(segments),
        n_modulations=n_modulations,
    )
