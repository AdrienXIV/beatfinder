"""Agrégation des analyses track-level en pattern playlist.

Pour chaque feature numérique : médiane, moyenne, std, p25, p75, min, max.
Pour chaque feature catégorielle (key, mode, root) : distribution + most common.
Pour les vecteurs (MFCC) : médiane et std element-wise.

Les médianes sont privilégiées dans le brief de production (elles encaissent
mieux les outliers que la moyenne).
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

# Features numériques utilisées pour la détection de sous-clusters par k-means.
# Path tuple → label affiché dans le brief.
CLUSTER_FEATURES: list[tuple[tuple[str, ...], str]] = [
    (("tempo", "bpm"), "bpm"),
    (("energy", "lufs_integrated"), "lufs"),
    (("energy", "dynamic_range_db"), "dr"),
    (("energy", "crest_factor_db"), "crest"),
    (("spectral", "band_energy", "sub"), "sub"),
    (("spectral", "band_energy", "bass"), "bass"),
    (("spectral", "band_energy", "mid"), "mid"),
    (("spectral", "band_energy", "high_mid"), "high_mid"),
    (("spectral", "centroid_hz"), "centroid"),
    (("structure", "drop_position_ratio"), "drop"),
]
MIN_TRACKS_FOR_CLUSTERING = 12
# Silhouette 0.10 = clusters faiblement séparés mais qualitativement informatifs sur
# des playlists rap où le style varie en continuum plutôt qu'en groupes distincts.
# Au-dessus de 0.20, on perd les playlists hétérogènes intéressantes.
MIN_SILHOUETTE = 0.10


def _stats_numeric(values: list[float | None]) -> dict[str, Any]:
    """Stats descriptives sur une liste de floats. Filtre None et non-finis."""
    arr = np.array(
        [v for v in values if v is not None and np.isfinite(v)],
        dtype=np.float64,
    )
    if len(arr) == 0:
        return {"n": 0}
    return {
        "n": int(len(arr)),
        "median": round(float(np.median(arr)), 3),
        "mean": round(float(np.mean(arr)), 3),
        "std": round(float(np.std(arr)), 3),
        "min": round(float(np.min(arr)), 3),
        "p25": round(float(np.percentile(arr, 25)), 3),
        "p75": round(float(np.percentile(arr, 75)), 3),
        "max": round(float(np.max(arr)), 3),
    }


def _stats_categorical(values: list[str | None]) -> dict[str, Any]:
    """Distribution d'une liste de catégories."""
    valid = [v for v in values if v]
    if not valid:
        return {"n": 0, "distribution": {}}
    counter = Counter(valid)
    total = sum(counter.values())
    return {
        "n": total,
        "most_common": counter.most_common(1)[0][0],
        "distribution": {k: round(v / total, 3) for k, v in counter.most_common()},
    }


def _stats_vector(vectors: list[list[float] | None]) -> dict[str, Any]:
    """Médiane et std element-wise sur une liste de vecteurs (MFCC)."""
    valid = [v for v in vectors if v]
    if not valid:
        return {"n": 0, "median": [], "std": []}
    arr = np.array(valid, dtype=np.float64)
    return {
        "n": int(len(valid)),
        "median": [round(float(x), 3) for x in np.median(arr, axis=0)],
        "std": [round(float(x), 3) for x in np.std(arr, axis=0)],
    }


def _get(d: dict | None, *path: str) -> Any:
    """Walk dict path, retourne None si un niveau manque."""
    val: Any = d
    for p in path:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
        if val is None:
            return None
    return val


def extract_subclusters(
    track_features: list[dict],
    max_k: int = 4,
) -> dict | None:
    """Détecte si la playlist contient des sous-clusters via k-means + silhouette.

    Retourne `None` si :
      - trop peu de tracks (< MIN_TRACKS_FOR_CLUSTERING)
      - meilleur silhouette < MIN_SILHOUETTE (clusters peu séparés)
      - sklearn indisponible (fallback silencieux)

    Sinon retourne un dict {n_clusters, silhouette, clusters: [...]} où chaque
    cluster contient ses tracks indices + médianes des features utilisées.
    """
    if len(track_features) < MIN_TRACKS_FOR_CLUSTERING:
        return None
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None

    # Build matrix : seules les tracks avec TOUTES les features sont gardées
    rows: list[list[float]] = []
    kept_indices: list[int] = []
    for idx, t in enumerate(track_features):
        row: list[float] = []
        ok = True
        for path, _ in CLUSTER_FEATURES:
            v = t
            for p in path:
                if not isinstance(v, dict):
                    v = None
                    break
                v = v.get(p)
                if v is None:
                    break
            if v is None or not np.isfinite(v):
                ok = False
                break
            row.append(float(v))
        if ok:
            rows.append(row)
            kept_indices.append(idx)
    if len(rows) < MIN_TRACKS_FOR_CLUSTERING:
        return None

    X = np.array(rows, dtype=np.float64)
    Xs = StandardScaler().fit_transform(X)

    best_k = None
    best_score = -1.0
    best_labels: np.ndarray | None = None
    upper = min(max_k, len(rows) - 1)
    for k in range(2, upper + 1):
        try:
            km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
        except Exception:  # noqa: BLE001  # KMeans peut crash sur features dégénérées (NaN, rang faible) — skip ce k
            continue
        labels = km.labels_
        if len(set(labels)) < k:
            continue
        try:
            score = silhouette_score(Xs, labels)
        except ValueError:
            continue
        if score > best_score:
            best_score = score
            best_k = k
            best_labels = labels

    if best_labels is None or best_score < MIN_SILHOUETTE:
        return None

    clusters: list[dict] = []
    for c in range(best_k):
        mask = best_labels == c
        c_indices_orig = [kept_indices[i] for i in np.where(mask)[0]]
        c_X = X[mask]
        medians = {
            label: round(float(np.median(c_X[:, i])), 3)
            for i, (_, label) in enumerate(CLUSTER_FEATURES)
        }
        clusters.append({
            "size": int(mask.sum()),
            "track_indices": c_indices_orig,
            "medians": medians,
        })
    # Tri clusters par taille décroissante (le plus représentatif en 1er)
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return {
        "n_clusters": best_k,
        "silhouette": round(float(best_score), 3),
        "n_tracks_used": len(rows),
        "clusters": clusters,
    }


def _compute_coherence_flags(pattern: dict, n_tracks: int) -> list[str]:
    """Détecte si les tracks d'un projet partent dans tous les sens.

    Heuristiques calibrées sur l'observation des playlists existantes :
    - BPM std > 15 → tempo trop éparpillé (Top Rap FR a std≈14)
    - Mode quasi-50/50 → la signature mineur/majeur n'est plus identifiable
    - Sub std > 0.15 → mix par bande trop hétérogène

    Retourne une liste de flags textuels parmi {"bpm", "mode", "sub"}.
    Vide si tracks cohérentes ou si moins de 2 tracks (rien à comparer).
    """
    if n_tracks < 2:
        return []
    flags: list[str] = []

    bpm_std = (pattern.get("tempo", {}) or {}).get("bpm", {}).get("std")
    if isinstance(bpm_std, (int, float)) and bpm_std > 15:
        flags.append("bpm")

    mode_dist = (pattern.get("tonality", {}) or {}).get("mode", {}).get("distribution") or {}
    minor = float(mode_dist.get("minor", 0.0))
    major = float(mode_dist.get("major", 0.0))
    if minor and major:
        balance = abs(minor - 0.5) * 2  # 1.0 = pur, 0 = parfait 50/50
        if balance < 0.30:
            flags.append("mode")

    sub_std = (
        (pattern.get("spectral", {}) or {}).get("band_energy", {}) or {}
    ).get("sub", {}).get("std")
    if isinstance(sub_std, (int, float)) and sub_std > 0.15:
        flags.append("sub")

    return flags


def extract_pattern(track_features: list[dict]) -> dict:
    """Agrège une liste de dicts `analyze_track()` en un pattern playlist."""
    if not track_features:
        return {"n_tracks": 0}

    n = len(track_features)

    spectral_bands = ("sub", "bass", "low_mid", "mid", "high_mid", "high")

    pattern: dict = {
        "n_tracks": n,
        "duration_sec": _stats_numeric(
            [_get(t, "duration_sec") for t in track_features]
        ),
        "tempo": {
            "bpm": _stats_numeric([_get(t, "tempo", "bpm") for t in track_features]),
            "bpm_raw": [
                round(float(v), 2)
                for v in (_get(t, "tempo", "bpm") for t in track_features)
                if v is not None and np.isfinite(v)
            ],
            "bpm_confidence": _stats_numeric(
                [_get(t, "tempo", "bpm_confidence") for t in track_features]
            ),
            "beat_consistency": _stats_numeric(
                [_get(t, "tempo", "beat_consistency") for t in track_features]
            ),
            "onset_density": _stats_numeric(
                [_get(t, "tempo", "onset_density") for t in track_features]
            ),
            "swing_ratio": _stats_numeric(
                [_get(t, "tempo", "swing_ratio") for t in track_features]
            ),
        },
        "tonality": {
            "key": _stats_categorical(
                [_get(t, "tonality", "key") for t in track_features]
            ),
            "note": _stats_categorical(
                [_get(t, "tonality", "note") for t in track_features]
            ),
            "mode": _stats_categorical(
                [_get(t, "tonality", "mode") for t in track_features]
            ),
            "most_common_root": _stats_categorical(
                [_get(t, "tonality", "most_common_root") for t in track_features]
            ),
            "reliable_note_distribution": _stats_categorical(
                [
                    _get(t, "tonality", "note") for t in track_features
                    if _get(t, "tonality", "methods_agree_all")
                ]
            ),
            "reliable_mode_distribution": _stats_categorical(
                [
                    _get(t, "tonality", "mode") for t in track_features
                    if _get(t, "tonality", "methods_agree_all")
                ]
            ),
            "ks_cens_key": _stats_categorical(
                [_get(t, "tonality", "ks_cens_key") for t in track_features]
            ),
            "ks_cqt_key": _stats_categorical(
                [_get(t, "tonality", "ks_cqt_key") for t in track_features]
            ),
            "madmom_key": _stats_categorical(
                [_get(t, "tonality", "madmom_key") for t in track_features]
            ),
            "uncertain_ratio": round(
                sum(
                    1 for t in track_features
                    if _get(t, "tonality", "is_uncertain")
                ) / n, 3,
            ),
            "all_agree_ratio": round(
                sum(
                    1 for t in track_features
                    if _get(t, "tonality", "methods_agree_all")
                ) / n, 3,
            ),
            "vote_count": _stats_numeric(
                [_get(t, "tonality", "vote_count") for t in track_features]
            ),
            "madmom_confidence": _stats_numeric(
                [_get(t, "tonality", "madmom_confidence") for t in track_features]
            ),
            "n_modulations": _stats_numeric(
                [_get(t, "tonality", "n_modulations") for t in track_features]
            ),
            "major_minor_ratio": _stats_numeric(
                [_get(t, "tonality", "major_minor_ratio") for t in track_features]
            ),
        },
        "energy": {
            "rms_mean": _stats_numeric(
                [_get(t, "energy", "rms_mean") for t in track_features]
            ),
            "lufs_integrated": _stats_numeric(
                [_get(t, "energy", "lufs_integrated") for t in track_features]
            ),
            "true_peak_db": _stats_numeric(
                [_get(t, "energy", "true_peak_db") for t in track_features]
            ),
            "crest_factor_db": _stats_numeric(
                [_get(t, "energy", "crest_factor_db") for t in track_features]
            ),
            "dynamic_range_db": _stats_numeric(
                [_get(t, "energy", "dynamic_range_db") for t in track_features]
            ),
        },
        "spectral": {
            "centroid_hz": _stats_numeric(
                [_get(t, "spectral", "centroid_hz") for t in track_features]
            ),
            "rolloff85_hz": _stats_numeric(
                [_get(t, "spectral", "rolloff85_hz") for t in track_features]
            ),
            "flatness": _stats_numeric(
                [_get(t, "spectral", "flatness") for t in track_features]
            ),
            "band_energy": {
                band: _stats_numeric(
                    [_get(t, "spectral", "band_energy", band) for t in track_features]
                )
                for band in spectral_bands
            },
        },
        "structure": {
            "n_sections": _stats_numeric(
                [_get(t, "structure", "n_sections") for t in track_features]
            ),
            "drop_position_ratio": _stats_numeric(
                [_get(t, "structure", "drop_position_ratio") for t in track_features]
            ),
        },
        "timbre": {
            "mfcc_mean": _stats_vector(
                [_get(t, "timbre", "mfcc_mean") for t in track_features]
            ),
            "mfcc_std": _stats_vector(
                [_get(t, "timbre", "mfcc_std") for t in track_features]
            ),
        },
        "subclusters": extract_subclusters(track_features),
    }
    pattern["coherence_flags"] = _compute_coherence_flags(pattern, n)
    return pattern


def build_single_track_pattern(features: dict) -> dict:
    """Wrap les features d'une track unique dans le même format que `extract_pattern`.

    Utile pour comparer une track individuelle contre un pattern playlist (ou une
    autre track) via `action_planner.generate_action_items()`. Pour chaque feature,
    median = mean = la valeur, std = 0. Pas de subclusters (1 seul point).
    """
    return extract_pattern([features])
