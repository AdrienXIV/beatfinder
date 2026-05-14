"""Génère une checklist d'actions actionnables pour rapprocher un projet d'une cible.

Compare deux patterns (from = projet courant, to = cible) et émet des
`ActionItem` groupés par catégorie (mastering / mix / rhythm / tonality /
structure) avec une priorité (high / medium / low) et une recommandation
texte calée sur le delta.

Le code est volontairement déclaratif et écrit règle par règle pour rester
modifiable : chaque heuristique est isolée, modifiable sans toucher
le dispatch.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Category = Literal["mastering", "mix", "rhythm", "tonality", "structure"]
Priority = Literal["high", "medium", "low"]


@dataclass(slots=True)
class ActionItem:
    key: str
    category: Category
    metric: str
    priority: Priority
    current: float | None
    target: float | None
    delta: float | None
    unit: str
    action: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _walk(d: dict | None, *path: str) -> Any:
    val: Any = d
    for p in path:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
        if val is None:
            return None
    return val


def _prio_lufs(delta: float) -> Priority:
    a = abs(delta)
    if a > 3.0:
        return "high"
    if a > 1.5:
        return "medium"
    return "low"


def _prio_pts(delta_pts: float, *, high: float, medium: float) -> Priority:
    a = abs(delta_pts)
    if a > high:
        return "high"
    if a > medium:
        return "medium"
    return "low"


def _prio_relative(current: float, target: float, *, high: float = 0.30, medium: float = 0.15) -> Priority:
    if target == 0:
        return "low"
    rel = abs(current - target) / abs(target)
    if rel > high:
        return "high"
    if rel > medium:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Mastering
# ---------------------------------------------------------------------------

def _mastering_items(p_from: dict, p_to: dict) -> list[ActionItem]:
    items: list[ActionItem] = []

    lufs_from = _walk(p_from, "energy", "lufs_integrated", "median")
    lufs_to = _walk(p_to, "energy", "lufs_integrated", "median")
    if lufs_from is not None and lufs_to is not None:
        delta = lufs_to - lufs_from
        if abs(delta) > 0.7:
            up = delta > 0
            items.append(ActionItem(
                key="mastering.lufs",
                category="mastering",
                metric="LUFS médian",
                priority=_prio_lufs(delta),
                current=round(lufs_from, 1),
                target=round(lufs_to, 1),
                delta=round(delta, 1),
                unit="dB",
                action=(
                    f"Pousser le master de +{abs(delta):.1f} dB "
                    "(compresseur bus + limiter ceiling à -0.3 dBTP)"
                    if up
                    else f"Réduire le master de {abs(delta):.1f} dB (moins de gain au mastering)"
                ),
                rationale=(
                    f"Tu es {abs(delta):.1f} dB "
                    f"{'sous le' if up else 'au-dessus du'} niveau de la cible."
                ),
            ))

    tp_from = _walk(p_from, "energy", "true_peak_db", "median")
    tp_to = _walk(p_to, "energy", "true_peak_db", "median")
    if tp_from is not None and tp_to is not None:
        delta = tp_to - tp_from
        if abs(delta) > 0.5:
            items.append(ActionItem(
                key="mastering.true_peak",
                category="mastering",
                metric="True peak",
                priority="medium" if abs(delta) > 1.0 else "low",
                current=round(tp_from, 1),
                target=round(tp_to, 1),
                delta=round(delta, 1),
                unit="dBFS",
                action=(
                    f"Régler le limiter ceiling autour de {tp_to:+.1f} dBTP "
                    f"(actuellement {tp_from:+.1f})"
                ),
                rationale="Le headroom du master n'est pas calé sur la cible.",
            ))

    cr_from = _walk(p_from, "energy", "crest_factor_db", "median")
    cr_to = _walk(p_to, "energy", "crest_factor_db", "median")
    if cr_from is not None and cr_to is not None:
        delta = cr_to - cr_from
        if abs(delta) > 1.0:
            items.append(ActionItem(
                key="mastering.crest",
                category="mastering",
                metric="Crest factor",
                priority=_prio_relative(cr_from, cr_to),
                current=round(cr_from, 1),
                target=round(cr_to, 1),
                delta=round(delta, 1),
                unit="dB",
                action=(
                    "Compresseur bus plus agressif (ratio 2:1, attaque 30 ms, release 100 ms)"
                    if delta < 0
                    else "Décompresser : ratio plus doux ou bypass du master compressor"
                ),
                rationale=(
                    "Crest factor trop élevé = pas assez compressé"
                    if delta < 0
                    else "Crest factor trop bas = trop compressé/écrasé"
                ),
            ))

    dr_from = _walk(p_from, "energy", "dynamic_range_db", "median")
    dr_to = _walk(p_to, "energy", "dynamic_range_db", "median")
    if dr_from is not None and dr_to is not None:
        delta = dr_to - dr_from
        if abs(delta) > 1.5:
            items.append(ActionItem(
                key="mastering.dr",
                category="mastering",
                metric="Dynamic range (p95-p10)",
                priority=_prio_relative(dr_from, dr_to),
                current=round(dr_from, 1),
                target=round(dr_to, 1),
                delta=round(delta, 1),
                unit="dB",
                action=(
                    "Réduire la dynamique : compresseur multibande léger sur le bus master"
                    if delta < 0
                    else "Préserver plus de dynamique : alléger la compression du bus"
                ),
                rationale=(
                    "Trop dynamique pour les standards streaming"
                    if delta < 0
                    else "Pas assez dynamique vs la cible"
                ),
            ))

    return items


# ---------------------------------------------------------------------------
# Mix — bandes spectrales + centroid + rolloff
# ---------------------------------------------------------------------------

# (band_key, label, prio_thresholds (high, medium) en pts %)
_BANDS: tuple[tuple[str, str, tuple[float, float]], ...] = (
    ("sub",       "Sub 20-60 Hz",       (15.0, 7.0)),
    ("bass",      "Bass 60-250 Hz",     (10.0, 5.0)),
    ("low_mid",   "Low-mid 250-500 Hz", (5.0, 2.5)),
    ("mid",       "Mid 500 Hz - 2 kHz", (6.0, 3.0)),
    ("high_mid",  "High-mid 2-6 kHz",   (1.5, 0.8)),
    ("high",      "High 6-20 kHz",      (1.0, 0.5)),
)

_BAND_ACTIONS_DOWN: dict[str, str] = {
    "sub":      "HP 30 Hz (high-pass filter) sur les samples non-sub, sidechain compressor plus marqué (kick → sub-bass)",
    "bass":     "Cleanup 60-250 Hz : EQ cut sur les samples qui masquent le kick (drums, FX), shelve down (atténuer les basses) sur les pads",
    "low_mid":  "Cut 250-500 Hz : enlève la boue (accumulation low-mid qui embrouille le mix), scoop EQ (creux en cloche) sur les pads/synthés trop chargés",
    "mid":      "Pull down 500 Hz - 2 kHz : EQ cut -2 à -4 dB en cloche pour réduire saturation/harmoniques sur les leads",
    "high_mid": "Atténuer 2-6 kHz (bande trop agressive) : de-esser (anti-sibilance) sur hats/percu, EQ -1 à -2 dB",
    "high":     "Adoucir 6-20 kHz (peut-être trop d'air) : shelf down (atténuer les aigus) ou low-pass à 16 kHz",
}

_BAND_ACTIONS_UP: dict[str, str] = {
    "sub":      "Booster sub-bass : EQ shelf +2 dB autour de 50 Hz, vérifier que la sub-bass est en mono (pas de stéréo dans les graves)",
    "bass":     "Booster 60-250 Hz : EQ shelf low, ajouter saturation harmonique (Decapitator, Saturator) sur la ligne de basse",
    "low_mid":  "Booster 250-500 Hz (warmth/chaleur sonore) : saturation sur drums pour épaissir, pads avec harmoniques basses",
    "mid":      "Booster 500 Hz - 2 kHz (présence des leads/voix) : EQ +1-2 dB en cloche sur la mélodie principale",
    "high_mid": "Ajouter présence 2-6 kHz : shelf +1-2 dB pour brillance sur hats/snares",
    "high":     "Plus d'air (au-delà de 6 kHz) : shelf +1-2 dB au-dessus de 8 kHz, ajouter cymbal sweeps / textures hautes",
}


def _mix_items(p_from: dict, p_to: dict) -> list[ActionItem]:
    items: list[ActionItem] = []

    for band, label, (hi, med) in _BANDS:
        v_from = _walk(p_from, "spectral", "band_energy", band, "median")
        v_to = _walk(p_to, "spectral", "band_energy", band, "median")
        if v_from is None or v_to is None:
            continue
        pts_from = v_from * 100.0
        pts_to = v_to * 100.0
        delta_pts = pts_to - pts_from
        if abs(delta_pts) < med * 0.5:
            continue
        priority = _prio_pts(delta_pts, high=hi, medium=med)
        action = _BAND_ACTIONS_DOWN[band] if delta_pts < 0 else _BAND_ACTIONS_UP[band]
        items.append(ActionItem(
            key=f"mix.band.{band}",
            category="mix",
            metric=label,
            priority=priority,
            current=round(pts_from, 1),
            target=round(pts_to, 1),
            delta=round(delta_pts, 1),
            unit="pts %",
            action=action,
            rationale=f"Cible {pts_to:.0f}% vs actuel {pts_from:.0f}%.",
        ))

    c_from = _walk(p_from, "spectral", "centroid_hz", "median")
    c_to = _walk(p_to, "spectral", "centroid_hz", "median")
    if c_from is not None and c_to is not None:
        delta = c_to - c_from
        if abs(delta) > 200:
            items.append(ActionItem(
                key="mix.centroid",
                category="mix",
                metric="Centroid spectral",
                priority=_prio_relative(c_from, c_to, high=0.30, medium=0.15),
                current=round(c_from, 0),
                target=round(c_to, 0),
                delta=round(delta, 0),
                unit="Hz",
                action=(
                    "Ouvrir le haut du spectre : shelf high +1 à +3 dB autour de 8 kHz, "
                    "moins de low-pass agressif sur les samples"
                    if delta > 0
                    else "Refermer le haut : de-esser, shelf high -1 dB, low-pass plus tôt"
                ),
                rationale=(
                    f"Spectre étouffé ({c_from:.0f} Hz) vs cible ({c_to:.0f} Hz)"
                    if delta > 0
                    else f"Spectre trop brillant ({c_from:.0f} Hz) vs cible ({c_to:.0f} Hz)"
                ),
            ))

    r_from = _walk(p_from, "spectral", "rolloff85_hz", "median")
    r_to = _walk(p_to, "spectral", "rolloff85_hz", "median")
    if r_from is not None and r_to is not None:
        delta = r_to - r_from
        if abs(delta) > 800:
            items.append(ActionItem(
                key="mix.rolloff",
                category="mix",
                metric="Rolloff 85%",
                priority=_prio_relative(r_from, r_to, high=0.35, medium=0.18),
                current=round(r_from, 0),
                target=round(r_to, 0),
                delta=round(delta, 0),
                unit="Hz",
                action=(
                    "Garder plus d'énergie dans le top : éviter de couper trop tôt, "
                    "ajouter textures hautes (cymbal sweeps, white noise FX)"
                    if delta > 0
                    else "Couper plus tôt dans le top : low-pass autour de 16 kHz, "
                    "moins d'air"
                ),
                rationale=f"Top coupé à {r_from:.0f} Hz vs cible {r_to:.0f} Hz.",
            ))

    return items


# ---------------------------------------------------------------------------
# Rhythm
# ---------------------------------------------------------------------------

def _rhythm_items(p_from: dict, p_to: dict) -> list[ActionItem]:
    items: list[ActionItem] = []

    bpm_from = _walk(p_from, "tempo", "bpm", "median")
    bpm_to = _walk(p_to, "tempo", "bpm", "median")
    if bpm_from is not None and bpm_to is not None:
        delta = bpm_to - bpm_from
        if abs(delta) > 4:
            items.append(ActionItem(
                key="rhythm.bpm_median",
                category="rhythm",
                metric="BPM médian",
                priority="medium" if abs(delta) > 8 else "low",
                current=round(bpm_from, 0),
                target=round(bpm_to, 0),
                delta=round(delta, 0),
                unit="BPM",
                action=(
                    f"Cibler des tempos plus rapides : essaie des beats à {bpm_to:.0f} BPM"
                    if delta > 0
                    else f"Cibler des tempos plus lents : essaie des beats à {bpm_to:.0f} BPM"
                ),
                rationale=f"Tu produis surtout à {bpm_from:.0f} BPM, la cible est à {bpm_to:.0f}.",
            ))

    std_from = _walk(p_from, "tempo", "bpm", "std")
    std_to = _walk(p_to, "tempo", "bpm", "std")
    if std_from is not None and std_to is not None:
        delta = std_to - std_from
        if abs(delta) > 2.0:
            items.append(ActionItem(
                key="rhythm.bpm_std",
                category="rhythm",
                metric="BPM std (variance tempo)",
                priority=_prio_relative(std_from, std_to, high=0.5, medium=0.25),
                current=round(std_from, 1),
                target=round(std_to, 1),
                delta=round(delta, 1),
                unit="BPM",
                action=(
                    f"Diversifier les tempos : actuellement très centré ±{std_from:.0f} BPM, "
                    f"la cible varie sur ±{std_to:.0f}. Vise au moins 3 tempos distincts dans ton catalogue."
                    if delta > 0
                    else "Cible plus resserrée en tempo : moins de variance dans tes BPM"
                ),
                rationale=(
                    "Catalogue mono-tempo, manque de variété"
                    if delta > 0
                    else "Catalogue trop éparpillé en tempo vs cible"
                ),
            ))

    od_from = _walk(p_from, "tempo", "onset_density", "median")
    od_to = _walk(p_to, "tempo", "onset_density", "median")
    if od_from is not None and od_to is not None:
        delta = od_to - od_from
        if abs(delta) > 0.4:
            items.append(ActionItem(
                key="rhythm.onset_density",
                category="rhythm",
                metric="Onset density",
                priority=_prio_relative(od_from, od_to, high=0.30, medium=0.15),
                current=round(od_from, 2),
                target=round(od_to, 2),
                delta=round(delta, 2),
                unit="onsets/sec",
                action=(
                    "Densifier les hats/percu : ajouter rolls, triplets, layers de percussions"
                    if delta > 0
                    else "Aérer le rythme : moins de hats/percu, plus de respiration"
                ),
                rationale=(
                    "Beats moins denses vs cible"
                    if delta > 0
                    else "Beats plus denses que la cible"
                ),
            ))

    return items


# ---------------------------------------------------------------------------
# Tonality
# ---------------------------------------------------------------------------

def _tonality_items(p_from: dict, p_to: dict) -> list[ActionItem]:
    items: list[ActionItem] = []

    mode_from = _walk(p_from, "tonality", "mode", "distribution") or {}
    mode_to = _walk(p_to, "tonality", "mode", "distribution") or {}
    minor_from = float(mode_from.get("minor", 0.0))
    minor_to = float(mode_to.get("minor", 0.0))
    if mode_from and mode_to:
        delta_pts = (minor_to - minor_from) * 100.0
        if abs(delta_pts) > 8:
            items.append(ActionItem(
                key="tonality.mode_minor",
                category="tonality",
                metric="Ratio mode mineur",
                priority=_prio_pts(delta_pts, high=20.0, medium=10.0),
                current=round(minor_from * 100.0, 0),
                target=round(minor_to * 100.0, 0),
                delta=round(delta_pts, 0),
                unit="pts %",
                action=(
                    "Produire plus de tracks en mineur (dorian, harmonic minor, natural minor) "
                    "— c'est la signature dominante de la cible"
                    if delta_pts > 0
                    else "Produire plus de tracks en majeur — la cible est plus claire que toi"
                ),
                rationale=f"Cible {minor_to * 100:.0f}% mineur vs actuel {minor_from * 100:.0f}%.",
            ))

    root_from = _walk(p_from, "tonality", "most_common_root", "most_common")
    root_to = _walk(p_to, "tonality", "most_common_root", "most_common")
    if root_from and root_to and root_from != root_to:
        items.append(ActionItem(
            key="tonality.root_dominant",
            category="tonality",
            metric="Tonalité dominante",
            priority="low",
            current=None,
            target=None,
            delta=None,
            unit="note",
            action=(
                f"Essaie de produire dans la tonalité dominante de la cible : {root_to}. "
                f"Tu reviens souvent en {root_from}."
            ),
            rationale=f"Cible majoritaire : {root_to}. Toi : {root_from}.",
        ))

    return items


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def _structure_items(p_from: dict, p_to: dict) -> list[ActionItem]:
    items: list[ActionItem] = []

    dp_from = _walk(p_from, "structure", "drop_position_ratio", "median")
    dp_to = _walk(p_to, "structure", "drop_position_ratio", "median")
    if dp_from is not None and dp_to is not None:
        delta = dp_to - dp_from
        if abs(delta) > 0.04:
            items.append(ActionItem(
                key="structure.drop_position",
                category="structure",
                metric="Position du drop (ratio)",
                priority=_prio_relative(dp_from, dp_to, high=0.30, medium=0.15),
                current=round(dp_from, 2),
                target=round(dp_to, 2),
                delta=round(delta, 2),
                unit="ratio",
                action=(
                    f"Drop plus tard : viser ~{dp_to * 100:.0f}% du track (intro + buildup plus longs)"
                    if delta > 0
                    else f"Drop plus tôt : viser ~{dp_to * 100:.0f}% du track (intro plus courte)"
                ),
                rationale=f"Cible : drop à {dp_to * 100:.0f}% vs actuel {dp_from * 100:.0f}%.",
            ))

    ns_from = _walk(p_from, "structure", "n_sections", "median")
    ns_to = _walk(p_to, "structure", "n_sections", "median")
    if ns_from is not None and ns_to is not None:
        delta = ns_to - ns_from
        if abs(delta) >= 1.0:
            items.append(ActionItem(
                key="structure.n_sections",
                category="structure",
                metric="Nombre de sections",
                priority="low" if abs(delta) < 2 else "medium",
                current=round(ns_from, 0),
                target=round(ns_to, 0),
                delta=round(delta, 0),
                unit="sections",
                action=(
                    f"Ajouter des variations / bridges (cible ~{ns_to:.0f} sections vs {ns_from:.0f})"
                    if delta > 0
                    else f"Simplifier la structure ({ns_to:.0f} sections vs {ns_from:.0f})"
                ),
                rationale="Plus de structure / sections variées" if delta > 0 else "Trop de découpe vs cible",
            ))

    dur_from = _walk(p_from, "duration_sec", "median")
    dur_to = _walk(p_to, "duration_sec", "median")
    if dur_from is not None and dur_to is not None:
        delta = dur_to - dur_from
        if abs(delta) > 25:
            items.append(ActionItem(
                key="structure.duration",
                category="structure",
                metric="Durée médiane",
                priority="low",
                current=round(dur_from, 0),
                target=round(dur_to, 0),
                delta=round(delta, 0),
                unit="sec",
                action=(
                    f"Étendre les tracks : la cible fait ~{dur_to:.0f}s en médiane"
                    if delta > 0
                    else f"Raccourcir les tracks : la cible fait ~{dur_to:.0f}s en médiane"
                ),
                rationale=f"Cible {dur_to:.0f}s vs actuel {dur_from:.0f}s.",
            ))

    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PRIORITY_ORDER: dict[Priority, int] = {"high": 0, "medium": 1, "low": 2}


def generate_action_items(
    pattern_from: dict | None, pattern_to: dict | None,
) -> list[dict[str, Any]]:
    """Retourne la liste des actions à mener pour rapprocher `from` de `to`.

    Tri : par catégorie (mastering, mix, rhythm, tonality, structure), puis par
    priorité (high → low) à l'intérieur de chaque catégorie.
    """
    if not pattern_from or not pattern_to:
        return []

    items: list[ActionItem] = []
    items.extend(_mastering_items(pattern_from, pattern_to))
    items.extend(_mix_items(pattern_from, pattern_to))
    items.extend(_rhythm_items(pattern_from, pattern_to))
    items.extend(_tonality_items(pattern_from, pattern_to))
    items.extend(_structure_items(pattern_from, pattern_to))

    category_order: dict[Category, int] = {
        "mastering": 0,
        "mix": 1,
        "rhythm": 2,
        "tonality": 3,
        "structure": 4,
    }
    items.sort(key=lambda it: (category_order[it.category], _PRIORITY_ORDER[it.priority]))
    return [it.to_dict() for it in items]
