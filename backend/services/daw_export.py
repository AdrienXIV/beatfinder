"""Export DAW : génère une chaîne master à partir d'un plan d'action.

Format unique : markdown descriptif universel (Live, FL, Logic, Reaper, Pro Tools).
Le markdown est autonome (préambule, glossaire) pour qu'un humain ou un assistant
IA puisse le lire sans contexte externe — même modèle que le brief de production
(cf. `report_generator/brief.py`).

Le mapping plan d'action → chaîne master :
- LUFS / true peak / crest / DR → Compressor + Limiter
- 6 bandes spectrales (sub/bass/low_mid/mid/high_mid/high) → EQ8 paramétrique
- centroid / rolloff → high-shelf si on ouvre le haut

Heuristique d'ajustement EQ :
  delta_pts ≈ pourcentage d'énergie à ajouter/retirer
  → conversion approximative : ±1 pt = ±0.3 dB en bell EQ (à Q=0.7)
  Cap à ±6 dB pour éviter les distortions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend import __version__

if TYPE_CHECKING:
    from backend.api.schemas import ActionPlanOut

log = logging.getLogger(__name__)


# Mapping 6 bandes spectrales → EQ8 bands (fréquence centre, type)
EQ_BANDS: tuple[tuple[str, float, str, float], ...] = (
    # key,    freq Hz,  type,           Q
    ("sub",     45.0,    "low_shelf",    0.7),
    ("bass",    150.0,   "bell",         0.7),
    ("low_mid", 350.0,   "bell",         0.7),
    ("mid",     1200.0,  "bell",         0.7),
    ("high_mid", 4000.0, "bell",         0.7),
    ("high",    10000.0, "high_shelf",   0.7),
)


@dataclass(slots=True)
class EQBand:
    label: str
    freq_hz: float
    band_type: str
    q: float
    gain_db: float  # ajustement à appliquer
    rationale: str


@dataclass(slots=True)
class CompressorSettings:
    threshold_db: float
    ratio: float
    attack_ms: float
    release_ms: float
    makeup_gain_db: float
    rationale: str


@dataclass(slots=True)
class LimiterSettings:
    ceiling_db: float
    release_ms: float
    gain_db: float
    rationale: str


@dataclass(slots=True)
class MasterChain:
    """Chaîne master complète à appliquer."""

    eq_bands: list[EQBand]
    compressor: CompressorSettings | None
    limiter: LimiterSettings | None
    from_name: str
    to_name: str
    notes: list[str]


def _item_by_key(items: list, key: str) -> object | None:
    """Récupère un ActionItem par sa key (`lufs`, `sub`, ...)."""
    for it in items:
        if getattr(it, "key", None) == key:
            return it
    return None


def _delta(item: object) -> float | None:
    """Lit le delta numérique d'un ActionItem, None si absent."""
    if item is None:
        return None
    d = getattr(item, "delta", None)
    return float(d) if isinstance(d, (int, float)) else None


def _gain_for_band_delta(delta_pts: float | None) -> float:
    """Convertit un delta en points d'énergie en ajustement dB pour un bell EQ.

    Heuristique : ±1 pt ≈ ±0.3 dB. Cap à ±6 dB.
    Si delta None ou |delta| < 1, retourne 0 (pas d'ajustement).
    """
    if delta_pts is None or abs(delta_pts) < 1.0:
        return 0.0
    gain = delta_pts * 0.3
    return max(-6.0, min(6.0, round(gain, 1)))


def build_master_chain(plan: "ActionPlanOut") -> MasterChain:
    """Construit la chaîne master à partir d'un ActionPlanOut."""
    items = plan.items
    notes: list[str] = []

    # ----- EQ8 : 6 bandes mapping -----
    eq_bands: list[EQBand] = []
    for key, freq, band_type, q in EQ_BANDS:
        item = _item_by_key(items, f"mix.band.{key}")
        delta = _delta(item)
        gain = _gain_for_band_delta(delta)
        if gain == 0 and item is None:
            continue
        rationale = ""
        if item is not None and hasattr(item, "action"):
            rationale = str(getattr(item, "action", "")).strip() or ""
        eq_bands.append(EQBand(
            label=key,
            freq_hz=freq,
            band_type=band_type,
            q=q,
            gain_db=gain,
            rationale=rationale,
        ))

    # ----- Compressor : viser le crest target -----
    crest_item = _item_by_key(items, "mastering.crest")
    compressor: CompressorSettings | None = None
    if crest_item is not None:
        current = getattr(crest_item, "current", None)
        target = getattr(crest_item, "target", None)
        if isinstance(current, (int, float)) and isinstance(target, (int, float)):
            crest_delta = current - target  # positif = trop dynamique → compresser
            if crest_delta > 2.0:
                # Trop dynamique → compression moyenne
                compressor = CompressorSettings(
                    threshold_db=-12.0,
                    ratio=3.0,
                    attack_ms=10.0,
                    release_ms=120.0,
                    makeup_gain_db=round(crest_delta * 0.5, 1),
                    rationale=f"Réduit le crest de {current:.1f} → {target:.1f} dB (track trop dynamique pour streaming)",
                )
            elif crest_delta < -2.0:
                # Pas assez dynamique → compression légère ou skip
                notes.append(
                    f"Crest actuel ({current:.1f} dB) déjà inférieur à la cible ({target:.1f} dB) — "
                    "ne pas compresser davantage."
                )
            else:
                compressor = CompressorSettings(
                    threshold_db=-10.0,
                    ratio=2.0,
                    attack_ms=20.0,
                    release_ms=100.0,
                    makeup_gain_db=2.0,
                    rationale=f"Compression légère pour homogénéiser (crest {current:.1f} dB, cible {target:.1f} dB)",
                )

    # ----- Limiter : viser le LUFS target -----
    lufs_item = _item_by_key(items, "mastering.lufs")
    limiter: LimiterSettings | None = None
    if lufs_item is not None:
        current = getattr(lufs_item, "current", None)
        target = getattr(lufs_item, "target", None)
        if isinstance(current, (int, float)) and isinstance(target, (int, float)):
            gain = round(target - current, 1)  # positif = booster
            limiter = LimiterSettings(
                ceiling_db=-0.5,
                release_ms=50.0,
                gain_db=gain,
                rationale=f"Pousse le LUFS de {current:.1f} → {target:.1f} dB (streaming standard)",
            )

    return MasterChain(
        eq_bands=eq_bands,
        compressor=compressor,
        limiter=limiter,
        from_name=plan.from_name,
        to_name=plan.to_name,
        notes=notes,
    )


def generate_markdown(chain: MasterChain) -> str:
    """Génère un guide markdown universel (Live / FL / Logic / Reaper).

    Structure alignée sur `report_generator/brief.py` :
    préambule + métadonnées + comment lire + glossaire + sections + footer.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    md: list[str] = []

    def _intro(text: str) -> None:
        """Intro vulgarisée en italique markdown pur (compatible parseurs)."""
        md.append(f"*{text}*")
        md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────
    md.append("# Plan d'action Beatfinder — chaîne master")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # À propos
    # ─────────────────────────────────────────────────────────────────────
    md.append("## À propos de ce document")
    md.append("")
    md.append(
        "**Beatfinder** est un outil d'analyse de patterns audio. Il compare "
        "une source (track ou playlist) à une cible de référence et calcule "
        "un **plan d'action mastering** (EQ + compression + limiteur) pour "
        "aligner ta production sur le style de la cible."
    )
    md.append("")
    md.append(
        "Ce document est un **guide pas-à-pas universel**, applicable dans "
        "n'importe quelle DAW (Ableton Live, FL Studio, Logic Pro, Reaper, "
        "Pro Tools). Les valeurs proposées sont des points de départ basés "
        "sur l'écart médian entre ta source et la cible — **ajuste à "
        "l'oreille** en bypass A/B avec une track de la cible comme référence."
    )
    md.append("")
    md.append(
        "Destiné à un **beatmaker / producer**, ou à un **assistant IA** qui "
        "l'accompagne (pour expliquer, résumer, répondre à des questions "
        "techniques). Toutes les définitions techniques sont fournies dans "
        "le glossaire ci-dessous."
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Métadonnées
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Métadonnées")
    md.append("")
    md.append("| Champ | Valeur |")
    md.append("|---|---|")
    md.append(f"| Source | {chain.from_name} |")
    md.append(f"| Cible | {chain.to_name} |")
    md.append(f"| Date de génération | {now} |")
    md.append(f"| Version Beatfinder | {__version__} |")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Comment lire ce document
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Comment lire ce document")
    md.append("")
    md.append(
        "Les valeurs proposées (gain dB, threshold, ratio…) sont calculées "
        "à partir de **l'écart médian entre la source et la cible** sur "
        "chaque feature mesurée. Ce ne sont pas des règles absolues : "
        "commence avec ces valeurs, puis ajuste à l'oreille."
    )
    md.append("")
    md.append("**Ordre d'application sur ton bus master :**")
    md.append("")
    md.append(
        "1. **EQ paramétrique 8 bandes** — corrige le profil spectral "
        "(6 bandes mesurées par Beatfinder)"
    )
    md.append(
        "2. **Compressor** — ajuste le crest factor (homogénéité dynamique "
        "entre les passages forts et calmes)"
    )
    md.append(
        "3. **Limiter** — pousse le LUFS au niveau de la cible (volume "
        "compétitif streaming)"
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Glossaire
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Glossaire")
    md.append("")
    md.append(
        "*Termes techniques utilisés dans ce document. À consulter si une "
        "définition manque.*"
    )
    md.append("")
    md.append(
        "- **EQ paramétrique** : égaliseur permettant de booster ou couper "
        "des fréquences précises avec une largeur (Q) et un type (bell, "
        "shelf, etc.)."
    )
    md.append(
        "- **Bell** : courbe en cloche centrée sur une fréquence donnée. "
        "Affecte aussi les fréquences voisines selon le Q."
    )
    md.append(
        "- **Low-shelf / High-shelf** : booste ou coupe tout ce qui est "
        "sous (low-shelf) ou au-dessus (high-shelf) d'une fréquence cible."
    )
    md.append(
        "- **Q** (*Quality factor*) : largeur de la courbe EQ. Q bas = "
        "courbe large (musical), Q haut = courbe étroite (chirurgical)."
    )
    md.append(
        "- **Threshold** : niveau (en dBFS) au-dessus duquel un "
        "compressor/limiter s'active."
    )
    md.append(
        "- **Ratio** : agressivité de la compression. 2:1 = doux, 4:1 = "
        "standard, 10:1+ = limiteur."
    )
    md.append(
        "- **Attack** : temps de réaction du compressor (en ms). Court = "
        "capture les transitoires ; long = laisse passer les attaques."
    )
    md.append(
        "- **Release** : temps de relâchement (en ms). Court = compression "
        "qui \"respire\" vite ; long = compression maintenue."
    )
    md.append(
        "- **Makeup gain** : gain à rajouter en sortie du compressor pour "
        "compenser la baisse de volume due à la compression."
    )
    md.append(
        "- **Ceiling** : plafond absolu en dBFS que le limiter ne laissera "
        "jamais dépasser."
    )
    md.append(
        "- **Crest factor** : ratio peak/RMS du signal. Élevé = peu "
        "compressé ; bas = compression marquée."
    )
    md.append(
        "- **LUFS** (*Loudness Units Full Scale*) : mesure normalisée du "
        "volume perçu (norme broadcast ITU BS.1770-4). Standard streaming : "
        "-14 LUFS."
    )
    md.append("")
    md.append("---")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 1. EQ paramétrique 8 bandes
    # ─────────────────────────────────────────────────────────────────────
    md.append("## EQ paramétrique 8 bandes")
    md.append("")
    _intro(
        "Première étape : corriger le profil spectral. Cette section liste "
        "les ajustements bande par bande pour aligner ta source sur le "
        "profil de la cible. Plugins natifs courants : Ableton EQ8, "
        "FL Parametric EQ 2, Logic Channel EQ, FabFilter Pro-Q 3."
    )
    if not chain.eq_bands or all(b.gain_db == 0 for b in chain.eq_bands):
        md.append(
            "_Pas d'ajustement EQ nécessaire — ton profil spectral est "
            "déjà aligné sur la cible._"
        )
    else:
        md.append("| Bande | Fréquence | Type | Q | Gain | Notes |")
        md.append("|---|---|---|---|---|---|")
        for b in chain.eq_bands:
            gain_str = f"{b.gain_db:+.1f} dB" if b.gain_db != 0 else "0 dB (ON ref)"
            md.append(
                f"| {b.label.replace('_', '-')} | "
                f"{b.freq_hz:.0f} Hz | "
                f"{b.band_type.replace('_', ' ')} | "
                f"{b.q:.1f} | "
                f"{gain_str} | "
                f"{b.rationale or '—'} |"
            )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 2. Compressor
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Compressor")
    md.append("")
    _intro(
        "Deuxième étape : ajuster la dynamique pour homogénéiser le mix. "
        "Le compressor réduit l'écart entre les passages forts et calmes, "
        "ce qui aide à pousser le LUFS sans dépasser le ceiling au "
        "limiter. Plugins natifs courants : Ableton Glue, FL Maximus, "
        "Logic Compressor, FabFilter Pro-C 2."
    )
    if chain.compressor is None:
        md.append(
            "_Pas de compression nécessaire — ton crest factor est déjà "
            "dans la cible._"
        )
    else:
        c = chain.compressor
        md.append(f"- **Threshold** : {c.threshold_db:.1f} dBFS")
        md.append(f"- **Ratio** : {c.ratio:.1f} : 1")
        md.append(f"- **Attack** : {c.attack_ms:.0f} ms")
        md.append(f"- **Release** : {c.release_ms:.0f} ms (ou Auto)")
        md.append(f"- **Makeup gain** : {c.makeup_gain_db:+.1f} dB")
        md.append("")
        md.append(f"_{c.rationale}_")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 3. Limiter
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Limiter")
    md.append("")
    _intro(
        "Dernière étape : pousser le volume final au niveau de la cible. "
        "Le limiter agit comme un compressor extrême (ratio infini) avec "
        "un ceiling absolu qu'il ne dépasse jamais. C'est lui qui rend ta "
        "track \"competitive\" en streaming. Plugins natifs courants : "
        "Ableton Limiter, FL Maximus, Logic Adaptive Limiter, FabFilter "
        "Pro-L 2."
    )
    if chain.limiter is None:
        md.append(
            "_Pas de limiteur nécessaire — ton LUFS est déjà à la cible._"
        )
    else:
        lim = chain.limiter
        md.append(f"- **Input gain** : {lim.gain_db:+.1f} dB")
        md.append(f"- **Ceiling** : {lim.ceiling_db:.1f} dBFS")
        md.append(f"- **Release** : {lim.release_ms:.0f} ms")
        md.append("")
        md.append(f"_{lim.rationale}_")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Notes (conditionnel)
    # ─────────────────────────────────────────────────────────────────────
    if chain.notes:
        md.append("## Notes")
        md.append("")
        _intro(
            "Remarques contextuelles détectées par Beatfinder qui méritent "
            "ton attention avant d'appliquer la chaîne."
        )
        for n in chain.notes:
            md.append(f"- {n}")
        md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Footer
    # ─────────────────────────────────────────────────────────────────────
    md.append("---")
    md.append("")
    md.append(
        f"*Plan d'action généré par Beatfinder v{__version__} le {now}. "
        "Les valeurs sont un point de départ — valide à l'oreille.*"
    )
    md.append("")

    return "\n".join(md)
