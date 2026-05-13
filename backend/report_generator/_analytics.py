"""Calculs analytiques sur les patterns : fit_score, détection bimodale, etc."""
from __future__ import annotations

from ._helpers import (
    BPM_BIMODAL_MIN_GAP,
    BPM_BIMODAL_VALLEY_RATIO,
    DROP_HIGH_VARIANCE_IQR,
    FIT_FEATURES,
    MIN_RELIABLE_TRACKS,
    _walk_pattern,
    _walk_value,
)


def _fit_score(track_features: dict | None, pattern: dict) -> float | None:
    """Score [0, 1] de représentativité de la track vis-à-vis de la playlist.

    Pour chaque feature pondérée : 1.0 si valeur dans p25-p75, 0.5 si entre min
    et p25 ou p75 et max, 0 sinon (sortie hors range complet, peu probable car
    pattern construit sur les tracks).
    """
    if track_features is None:
        return None
    total_weight = 0.0
    score = 0.0
    for path, weight in FIT_FEATURES:
        # Pour spectral.band_energy.X, le path pattern est spectral.band_energy.X
        # qui contient le dict stats (p25, p75, etc.)
        stats = _walk_pattern(pattern, *path)
        val = _walk_value(track_features, *path)
        if stats is None or val is None:
            continue
        p25 = stats.get("p25")
        p75 = stats.get("p75")
        lo = stats.get("min")
        hi = stats.get("max")
        if p25 is None or p75 is None or lo is None or hi is None:
            continue
        if p25 <= val <= p75:
            score += weight
        elif lo <= val <= hi:
            score += weight * 0.5
        total_weight += weight
    if total_weight == 0:
        return None
    return round(score / total_weight, 3)


def _detect_bpm_clusters(raw: list[float], bin_size: float = 5.0) -> list[tuple[float, int]]:
    """Détecte si le BPM est uni- ou bi-modal via gap analysis.

    Retourne une liste de (centre_cluster, n_tracks) — vide si distribution
    plate. Si len == 1 → unimodal. Si len == 2 → bimodal avec gap >= 20 BPM.
    L'analyse est délibérément conservative pour éviter des faux positifs sur
    petit n.
    """
    if not raw or len(raw) < 10:
        return []
    vals = sorted(raw)
    lo = vals[0]
    hi = vals[-1]
    if hi - lo < BPM_BIMODAL_MIN_GAP:
        return []
    n_bins = max(6, int((hi - lo) / bin_size) + 1)
    edges = [lo + i * (hi - lo) / n_bins for i in range(n_bins + 1)]
    counts = [0] * n_bins
    for v in vals:
        idx = min(int((v - lo) / (hi - lo) * n_bins), n_bins - 1)
        counts[idx] += 1
    peak_count = max(counts)
    valley_threshold = peak_count * BPM_BIMODAL_VALLEY_RATIO
    # Trouver les pics locaux + vallées
    peaks: list[int] = []
    for i, c in enumerate(counts):
        if c == peak_count or (
            c >= valley_threshold * 2
            and (i == 0 or c >= counts[i - 1])
            and (i == n_bins - 1 or c >= counts[i + 1])
        ):
            peaks.append(i)
    if len(peaks) < 2:
        return []
    # Pour qu'on déclare bimodal, il faut une vraie vallée entre 2 pics
    p1 = peaks[0]
    p2 = peaks[-1]
    if (edges[p2] + edges[p2 + 1]) / 2 - (edges[p1] + edges[p1 + 1]) / 2 < BPM_BIMODAL_MIN_GAP:
        return []
    valley_min = min(counts[p1 + 1: p2]) if p2 > p1 + 1 else peak_count
    if valley_min > valley_threshold:
        return []

    def cluster_stats(peak_idx: int) -> tuple[float, int]:
        bins_in_cluster = range(max(0, peak_idx - 1), min(n_bins, peak_idx + 2))
        total_count = sum(counts[i] for i in bins_in_cluster)
        if total_count == 0:
            return ((edges[peak_idx] + edges[peak_idx + 1]) / 2, 0)
        weighted = sum(
            counts[i] * (edges[i] + edges[i + 1]) / 2
            for i in bins_in_cluster
        )
        return (weighted / total_count, total_count)
    return [cluster_stats(p1), cluster_stats(p2)]


def _root_dist_and_n(tonality: dict) -> tuple[dict, int, bool]:
    """Retourne (distribution_root, n_tracks_used, is_filtered).

    Préfère la distribution filtrée sur les tracks avec consensus 3/3 (votes
    convergent). Fallback sur la distribution complète si trop peu de tracks
    fiables (sinon les pourcentages sont des artefacts sur petit n).
    """
    reliable = tonality.get("reliable_note_distribution") or {}
    n_reliable = reliable.get("n", 0)
    if n_reliable >= MIN_RELIABLE_TRACKS:
        return (reliable.get("distribution") or {}, n_reliable, True)
    return (
        tonality.get("note", {}).get("distribution") or {},
        tonality.get("note", {}).get("n", 0),
        False,
    )


def _drop_variance_label(drop_stats: dict) -> tuple[str, bool]:
    """Retourne (label, is_high_variance) pour le drop_position_ratio.

    Si IQR > 25 points de pourcentage, on considère que le drop n'a pas de
    pattern stable (l'écart type n'est pas un proxy fiable car borné à 0-1).
    Dans ce cas, mieux vaut signaler "très variable" plutôt que recommander
    une médiane non actionnable.
    """
    p25 = drop_stats.get("p25")
    p75 = drop_stats.get("p75")
    median = drop_stats.get("median")
    if p25 is None or p75 is None or median is None:
        return ("position drop inconnue", True)
    iqr = p75 - p25
    if iqr > DROP_HIGH_VARIANCE_IQR:
        return (
            f"drop très variable ({p25 * 100:.0f}–{p75 * 100:.0f}% du track) "
            f"— pas de pattern fiable, ne pas s'aligner aveuglément",
            True,
        )
    return (
        f"drop entre {p25 * 100:.0f}–{p75 * 100:.0f}% (médiane {median * 100:.0f}%) "
        f"— pattern cohérent",
        False,
    )
