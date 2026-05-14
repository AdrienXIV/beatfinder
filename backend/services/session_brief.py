"""Génère un plan A→Z 'from-scratch' pour une session guidée.

À l'inverse de `report_generator.brief.generate_brief()` (qui décrit une
playlist) et de `services.action_planner.generate_action_items()` (qui
diff 2 patterns existants), ce générateur produit un **guide de démarrage**
calé sur un pattern cible : c'est ce qu'il faut savoir avant d'ouvrir la
DAW pour produire dans ce style.

Contenu :
- Préambule + métadonnées (cible figée, ambiance)
- Glossaire des termes techniques
- Tempo cible, tonalité, structure, profil spectral, master target
- Conseils ambiance (si renseignée)
- Footer

Format markdown autonome (préambule + glossaire) pour qu'un assistant IA
puisse l'utiliser sans contexte externe.
"""
from __future__ import annotations

from datetime import datetime

from backend import __version__


def _extract_top_root(tonality: dict) -> tuple[str | None, float]:
    """Extrait (note racine majoritaire, ratio) depuis un dict tonality.

    Gère 2 formats :
    - **Playlist agrégée** (extract_pattern sur N>1 tracks) : `distribution` /
      `distribution_filtered` sont des `{note: ratio}` plats.
    - **Track wrapped** (extract_pattern sur 1 track) : `note`,
      `reliable_note_distribution`, `most_common_root` sont des structs nested
      `{n, most_common, distribution}`.

    Retourne (None, 0.0) si aucune source exploitable.
    """
    # Format playlist : dict {note: ratio} direct
    for key in ("distribution_filtered", "distribution"):
        d = tonality.get(key)
        if isinstance(d, dict) and d:
            first_val = next(iter(d.values()))
            if isinstance(first_val, (int, float)):
                root, ratio = next(iter(d.items()))
                return root, float(ratio)

    # Format track wrapped : structure nested
    for key in ("reliable_note_distribution", "note", "most_common_root"):
        nested = tonality.get(key)
        if isinstance(nested, dict):
            inner = nested.get("distribution")
            if isinstance(inner, dict) and inner:
                root, ratio = next(iter(inner.items()))
                return root, float(ratio)
            mc = nested.get("most_common")
            if isinstance(mc, str) and mc:
                return mc, 1.0

    return None, 0.0


def generate_session_brief(
    target_pattern: dict,
    *,
    target_name: str = "Cible",
    ambiance: dict | None = None,
) -> str:
    """Renvoie le markdown du plan A→Z pour démarrer une track.

    Args:
        target_pattern: pattern cible (sortie de `extract_pattern`).
        target_name: nom affiché de la cible.
        ambiance: réponses ambiance optionnelles (Phase 2). Format libre,
            ex: {"mood": "sombre", "tempo_offset": "plus lent"}.
    """
    now = datetime.now().strftime("%Y-%m-%d")

    tempo = target_pattern.get("tempo", {})
    energy = target_pattern.get("energy", {})
    spectral = target_pattern.get("spectral", {})
    structure = target_pattern.get("structure", {})
    tonality = target_pattern.get("tonality", {})

    bpm_med = (tempo.get("bpm") or {}).get("median", 0)
    bpm_p25 = (tempo.get("bpm") or {}).get("p25", 0)
    bpm_p75 = (tempo.get("bpm") or {}).get("p75", 0)
    lufs_med = (energy.get("lufs_integrated") or {}).get("median", 0)
    tp_med = (energy.get("true_peak_db") or {}).get("median", 0)
    crest_med = (energy.get("crest_factor_db") or {}).get("median", 0)
    dr_med = (energy.get("dynamic_range_db") or {}).get("median", 0)
    drop_pct = ((structure.get("drop_position_ratio") or {}).get("median", 0)) * 100
    n_sections = (structure.get("n_sections") or {}).get("median", 0)
    dur_med = (target_pattern.get("duration_sec") or {}).get("median", 0)

    bands = spectral.get("band_energy") or {}
    sub_pct = (bands.get("sub") or {}).get("median", 0) * 100
    bass_pct = (bands.get("bass") or {}).get("median", 0) * 100
    low_mid_pct = (bands.get("low_mid") or {}).get("median", 0) * 100
    mid_pct = (bands.get("mid") or {}).get("median", 0) * 100
    high_mid_pct = (bands.get("high_mid") or {}).get("median", 0) * 100
    high_pct = (bands.get("high") or {}).get("median", 0) * 100

    mode_dist = (tonality.get("mode") or {}).get("distribution", {})
    minor_pct = mode_dist.get("minor", 0) * 100
    top_root, _root_ratio = _extract_top_root(tonality)
    mode_label = "minor" if minor_pct >= 50 else "major"
    if top_root:
        tonality_full = f"{top_root} {mode_label}"
    else:
        tonality_full = "tonalité non détectée"

    md: list[str] = []

    def _intro(text: str) -> None:
        md.append(f"*{text}*")
        md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────
    md.append(f"# Plan A→Z — démarrer une track inspirée par {target_name}")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Préambule
    # ─────────────────────────────────────────────────────────────────────
    md.append("## À propos de ce document")
    md.append("")
    md.append(
        "Ce plan est généré par **Beatfinder** pour t'aider à démarrer une "
        "track sans inspiration claire mais avec une direction précise : "
        "celle de la cible d'inspiration que tu as choisie. Toutes les "
        "valeurs ci-dessous sont **les médianes statistiques** de la cible "
        "— ce sont des points de départ à viser, pas des règles absolues."
    )
    md.append("")
    md.append(
        "Le workflow recommandé : tu démarres ta prod en suivant ce plan, "
        "puis tu importes des versions successives (v1, v2, …) pour mesurer "
        "ta convergence vers la cible via un **fit_score**. À chaque "
        "version, tu réajustes selon les écarts identifiés."
    )
    md.append("")
    md.append(
        "Destiné à un **beatmaker / producer**, ou à un **assistant IA** "
        "qui l'accompagne. Toutes les définitions techniques sont fournies "
        "dans le glossaire ci-dessous."
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Métadonnées
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Métadonnées")
    md.append("")
    md.append("| Champ | Valeur |")
    md.append("|---|---|")
    md.append(f"| Cible d'inspiration | {target_name} |")
    md.append(f"| Date de génération | {now} |")
    md.append(f"| Version Beatfinder | {__version__} |")
    if ambiance:
        for k, v in ambiance.items():
            md.append(f"| Ambiance ({k}) | {v} |")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Glossaire
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Glossaire")
    md.append("")
    md.append(
        "*Termes techniques utilisés dans ce plan. À consulter si une "
        "définition manque.*"
    )
    md.append("")
    md.append("- **BPM** (*Beats Per Minute*) : vitesse rythmique.")
    md.append(
        "- **LUFS** (*Loudness Units Full Scale*) : volume perçu normé "
        "streaming. -14 LUFS = standard Spotify ; -10 LUFS = master poussé."
    )
    md.append(
        "- **True peak (TP)** : niveau crête en dBFS. 0 dBFS = saturation, "
        "TP > 0 = inter-sample clipping."
    )
    md.append(
        "- **Crest factor** : ratio peak/RMS. Élevé (>14 dB) = peu "
        "compressé ; bas (<8 dB) = compression marquée."
    )
    md.append(
        "- **DR** (*Dynamic Range*) : contraste macro intro/drop (p95-p10)."
    )
    md.append(
        "- **Bandes spectrales** : sub (20-60 Hz), bass (60-250), low-mid "
        "(250-500), mid (500-2k), high-mid (2-6k), high (6-20k)."
    )
    md.append(
        "- **Mode** : majeur (lumineux) ou mineur (sombre)."
    )
    md.append(
        "- **Drop** : moment de plus haute énergie du track (souvent "
        "l'entrée du refrain principal)."
    )
    md.append(
        "- **fit_score** : % de features de ta version qui tombent dans "
        "le p25-p75 (cluster central) de la cible. 100% = au cœur du style."
    )
    md.append("")
    md.append("---")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 1. Tempo cible
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Tempo cible")
    md.append("")
    _intro(
        "Le BPM est la première décision à prendre avant d'ouvrir ta DAW. "
        "Configure-le dès la création du projet."
    )
    md.append(f"- **BPM cible** : **{bpm_med:.0f}**")
    md.append(f"- **Plage recommandée** : {bpm_p25:.0f}–{bpm_p75:.0f} BPM")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 2. Tonalité cible
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Tonalité cible")
    md.append("")
    _intro(
        "La clé musicale détermine l'ambiance harmonique. Écris ta mélodie "
        "et tes basses dans cette tonalité pour qu'elles sonnent cohérentes."
    )
    md.append(
        f"- **Mode majoritaire** : {'mineur' if minor_pct >= 50 else 'majeur'} "
        f"({minor_pct:.0f}% mineur dans la cible)"
    )
    if top_root:
        md.append(f"- **Racine la plus fréquente** : `{top_root}`")
    md.append(f"- **Tonalité recommandée** : `{tonality_full}`")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 3. Structure cible
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Structure cible")
    md.append("")
    _intro(
        "Combien de sections (intro / couplet / drop / pont / outro) et à "
        "quel moment placer le drop principal."
    )
    md.append(f"- **Drop principal** : à ~{drop_pct:.0f}% du track")
    md.append(f"- **Durée médiane** : {dur_med:.0f}s")
    md.append(f"- **Nombre de sections** : {n_sections:.0f} en moyenne")
    if dur_med > 0:
        drop_sec = int(dur_med * drop_pct / 100)
        md.append(
            f"- **Drop en secondes** : ~{drop_sec}s sur un track de "
            f"{dur_med:.0f}s"
        )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 4. Profil spectral cible
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Profil spectral cible")
    md.append("")
    _intro(
        "Répartition de l'énergie sonore entre les graves et les aigus. "
        "Ces pourcentages guident ton mix : combien de sub, de basse, de "
        "présence, etc."
    )
    md.append("| Bande | Plage | Cible |")
    md.append("|---|---|---|")
    md.append(f"| Sub | 20–60 Hz | **{sub_pct:.0f}%** |")
    md.append(f"| Bass | 60–250 Hz | **{bass_pct:.0f}%** |")
    md.append(f"| Low-mid | 250–500 Hz | {low_mid_pct:.0f}% |")
    md.append(f"| Mid | 500 Hz – 2 kHz | {mid_pct:.0f}% |")
    md.append(f"| High-mid | 2–6 kHz | {high_mid_pct:.0f}% |")
    md.append(f"| High | 6–20 kHz | {high_pct:.0f}% |")
    md.append("")
    md.append(
        f"- **Total low-end** (sub + bass) : **{sub_pct + bass_pct:.0f}%** "
        "sous 250 Hz"
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 5. Master target
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Master target")
    md.append("")
    _intro(
        "Les valeurs à viser sur ton bus master en fin de production. "
        "Garde-les en tête pendant le mix pour ne pas avoir de surprise au "
        "mastering."
    )
    md.append(f"- **LUFS intégré** : **{lufs_med:.1f} dB**")
    md.append(f"- **True peak** : {tp_med:+.1f} dBFS")
    md.append(f"- **Crest factor** : {crest_med:.1f} dB")
    md.append(f"- **Dynamic range** : {dr_med:.1f} dB")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 6. Conseils ambiance (si renseignée)
    # ─────────────────────────────────────────────────────────────────────
    if ambiance:
        md.append("## Conseils ambiance")
        md.append("")
        _intro(
            "Ajustements suggérés selon les réponses à l'étape ambiance du "
            "wizard. Affinent le plan ci-dessus selon tes intentions."
        )
        for k, v in ambiance.items():
            md.append(f"- **{k}** : {v}")
        md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # 7. Avant de démarrer la DAW
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Avant de démarrer ta DAW")
    md.append("")
    _intro(
        "Checklist préparatoire pour ne pas te perdre une fois dans le projet."
    )
    md.append(f"1. Crée un nouveau projet à **{bpm_med:.0f} BPM**")
    md.append(f"2. Définis la tonalité du projet en **{tonality_full}**")
    md.append(
        "3. Charge un kit de drums adapté au profil spectral cible "
        f"(low-end ~{sub_pct + bass_pct:.0f}%)"
    )
    md.append(
        f"4. Vise une longueur de **{dur_med:.0f}s** avec drop à "
        f"~{drop_pct:.0f}%"
    )
    md.append(
        f"5. Mastering final à **{lufs_med:.1f} LUFS** "
        f"(ceiling {tp_med:+.1f} dBFS)"
    )
    md.append("")
    md.append(
        "Une fois ta première version prête, importe-la dans la session pour "
        "obtenir ton premier **fit_score** et identifier les écarts à corriger."
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Footer
    # ─────────────────────────────────────────────────────────────────────
    md.append("---")
    md.append("")
    md.append(
        f"*Plan A→Z généré par Beatfinder v{__version__} le {now}. "
        "Les valeurs sont des points de départ — valide à l'oreille.*"
    )
    md.append("")

    return "\n".join(md)
