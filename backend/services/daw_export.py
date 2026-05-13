"""Export DAW : génère une chaîne master à partir d'un plan d'action.

2 formats :
- Markdown descriptif (universel : Live, FL, Logic, Reaper, Pro Tools)
- .adg Ableton (expérimental : XML gzippé, peut être refusé par Live selon version)

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

import gzip
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

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
    """Génère un guide markdown universel (Live / FL / Logic / Reaper)."""
    lines: list[str] = []
    lines.append(f"# Chaîne master Beatfinder")
    lines.append("")
    lines.append(f"**Source** : {chain.from_name}")
    lines.append(f"**Cible** : {chain.to_name}")
    lines.append(f"**Généré le** : {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append("> Applique cette chaîne sur ton bus master dans l'ordre. Les valeurs sont des points de départ basés sur l'écart médian entre ta source et la cible. Ajuste à l'oreille.")
    lines.append("")

    # EQ
    lines.append("## 1. EQ paramétrique 8 bandes")
    lines.append("")
    lines.append("Plugin natif (Ableton EQ8 / FL Parametric EQ 2 / Logic Channel EQ / FabFilter Pro-Q 3).")
    lines.append("")
    if not chain.eq_bands or all(b.gain_db == 0 for b in chain.eq_bands):
        lines.append("_Pas d'ajustement EQ nécessaire — ton profil spectral est déjà aligné._")
    else:
        lines.append("| Bande | Fréquence | Type | Q | Gain | Notes |")
        lines.append("|---|---|---|---|---|---|")
        for b in chain.eq_bands:
            gain_str = f"{b.gain_db:+.1f} dB" if b.gain_db != 0 else "0 dB (ON ref)"
            lines.append(
                f"| {b.label.replace('_', '-')} | {b.freq_hz:.0f} Hz | {b.band_type.replace('_', ' ')} | {b.q:.1f} | {gain_str} | {b.rationale or '—'} |"
            )
    lines.append("")

    # Compressor
    lines.append("## 2. Compressor")
    lines.append("")
    lines.append("Plugin natif (Ableton Glue / FL Maximus / Logic Compressor / FabFilter Pro-C 2).")
    lines.append("")
    if chain.compressor is None:
        lines.append("_Pas de compression nécessaire — ton crest factor est déjà dans la cible._")
    else:
        c = chain.compressor
        lines.append(f"- **Threshold** : {c.threshold_db:.1f} dBFS")
        lines.append(f"- **Ratio** : {c.ratio:.1f} : 1")
        lines.append(f"- **Attack** : {c.attack_ms:.0f} ms")
        lines.append(f"- **Release** : {c.release_ms:.0f} ms (ou Auto)")
        lines.append(f"- **Makeup gain** : {c.makeup_gain_db:+.1f} dB")
        lines.append("")
        lines.append(f"_{c.rationale}_")
    lines.append("")

    # Limiter
    lines.append("## 3. Limiter")
    lines.append("")
    lines.append("Plugin natif (Ableton Limiter / FL Maximus / Logic Adaptive Limiter / FabFilter Pro-L 2).")
    lines.append("")
    if chain.limiter is None:
        lines.append("_Pas de limiteur nécessaire — ton LUFS est déjà à la cible._")
    else:
        lim = chain.limiter
        lines.append(f"- **Input gain** : {lim.gain_db:+.1f} dB")
        lines.append(f"- **Ceiling** : {lim.ceiling_db:.1f} dBFS")
        lines.append(f"- **Release** : {lim.release_ms:.0f} ms")
        lines.append("")
        lines.append(f"_{lim.rationale}_")
    lines.append("")

    # Notes
    if chain.notes:
        lines.append("## Notes")
        lines.append("")
        for n in chain.notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Généré par Beatfinder. La chaîne est un point de départ : valide à l'oreille.")
    return "\n".join(lines)


def generate_ableton_adg(chain: MasterChain) -> bytes:
    """Génère un fichier .adg Ableton Audio Effect Rack (XML gzippé).

    EXPÉRIMENTAL : Live peut refuser le fichier si la version XML schema ne match pas.
    Le rack ne contient pas de devices Ableton réels (EQ8/Compressor/Limiter ont des
    structures XML complexes propriétaires) — c'est un rack vide nommé qu'Adrien peut
    remplir manuellement avec les paramètres du markdown.

    Si Live refuse l'ouverture, utilise le markdown à la place.
    """
    chain_name = f"Beatfinder · {chain.from_name} → {chain.to_name}"
    annotation = []
    for b in chain.eq_bands:
        if b.gain_db != 0:
            annotation.append(f"{b.label}@{b.freq_hz:.0f}Hz {b.gain_db:+.1f}dB")
    if chain.compressor:
        annotation.append(f"Comp T={chain.compressor.threshold_db:.0f} R={chain.compressor.ratio:.0f}")
    if chain.limiter:
        annotation.append(f"Limit gain={chain.limiter.gain_db:+.1f} ceil={chain.limiter.ceiling_db:.1f}")
    annotation_text = " | ".join(annotation) or "Pas d'ajustement"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="11.0_433" SchemaChangeCount="3" Creator="Beatfinder">
<GroupDevicePreset>
  <OverwriteProtectionNumber Value="0"/>
  <Device>
    <AudioEffectGroupDevice>
      <LomId Value="0"/>
      <UserName Value="{_xml_escape(chain_name)}"/>
      <Annotation Value="{_xml_escape(annotation_text)}"/>
      <SourceContext>
        <Value/>
      </SourceContext>
    </AudioEffectGroupDevice>
  </Device>
  <BranchPresets/>
</GroupDevicePreset>
</Ableton>
"""
    return gzip.compress(xml.encode("utf-8"))


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
