"""Rendu markdown du brief de production.

Compose un brief texte structuré (préambule + métadonnées + glossaire +
sections analytiques + sections action + méthodologie) à partir d'un pattern
playlist. Pas de LLM — règles déterministes. Délègue les calculs aux modules
`_analytics` et `_recommendations`.

Le markdown produit est volontairement autonome (préambule, glossaire,
sommaire) pour qu'un humain ou un assistant IA puisse le lire et le
comprendre sans contexte externe.

Le numéro de version affiché dans le brief (section "Méthodologie") est
résolu dynamiquement via `backend.__version__` (lu depuis `pyproject.toml`).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from backend import __version__

from ._analytics import (
    _detect_bpm_clusters,
    _drop_variance_label,
    _fit_score,
    _root_dist_and_n,
)
from ._helpers import (
    _band_bar,
    _interpret_centroid,
    _interpret_dr,
    _interpret_drop,
    _interpret_flatness,
    _interpret_lufs,
    _interpret_onset,
    _interpret_tp,
    _spectral_profile_label,
)
from ._recommendations import _eq_actions, _to_avoid, _to_copy


def generate_brief(
    pattern: dict,
    *,
    playlist_name: str = "Playlist",
    tracks_data: list[dict] | None = None,
) -> str:
    """Renvoie un brief de production markdown actionnable et autonome.

    Args:
        pattern: sortie de `pattern_extractor.extract_pattern()`.
        playlist_name: nom à afficher dans le titre.
        tracks_data: liste optionnelle de dicts {artist, title, features} pour
            la table per-track.
    """
    now = datetime.now().strftime("%Y-%m-%d")
    n = pattern.get("n_tracks", 0)
    if n == 0:
        return f"# {playlist_name}\n\n_Pas de tracks analysés._\n"

    tempo = pattern["tempo"]
    energy = pattern["energy"]
    spectral = pattern["spectral"]
    structure = pattern["structure"]
    tonality = pattern["tonality"]

    bpm_med = tempo["bpm"]["median"]
    bpm_p25 = tempo["bpm"]["p25"]
    bpm_p75 = tempo["bpm"]["p75"]
    lufs_med = energy["lufs_integrated"]["median"]
    tp_med = energy["true_peak_db"]["median"]
    sub_pct = spectral["band_energy"]["sub"]["median"] * 100
    bass_pct = spectral["band_energy"]["bass"]["median"] * 100
    drop_pct = structure["drop_position_ratio"]["median"] * 100
    dur_med = pattern["duration_sec"]["median"]

    mode_dist = tonality["mode"]["distribution"]
    minor_pct = mode_dist.get("minor", 0) * 100
    root_dist, root_n_used, root_is_filtered = _root_dist_and_n(tonality)
    top_root, top_root_pct = (
        next(iter(root_dist.items())) if root_dist else ("?", 0.0)
    )
    all_agree_pct = tonality.get("all_agree_ratio", 0) * 100
    n_reliable = round(all_agree_pct * n / 100)

    md: list[str] = []

    def _intro(text: str) -> None:
        """Ajoute un paragraphe d'intro vulgarisé sous un titre `##`.

        Convention markdown pure : un paragraphe entièrement en italique
        (`*texte*`) après un titre. Le CSS de `BriefRenderer.svelte` cible
        ces paragraphes via `p:has(em:only-child)` pour les afficher en
        police plus petite et couleur muted. Format compatible avec tout
        parseur markdown standard (humain, IA, autres outils).
        """
        md.append(f"*{text}*")
        md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────
    md.append(f"# Brief Beatfinder — {playlist_name}")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Préambule : à propos + audience
    # ─────────────────────────────────────────────────────────────────────
    md.append("## À propos de ce document")
    md.append("")
    md.append(
        "**Beatfinder** est un outil d'analyse de patterns audio. Il compare "
        "une playlist (Spotify ou fichiers locaux) à ses tracks pour en "
        "extraire des règles statistiques actionnables : tempo, tonalité, "
        "profil spectral, mastering, structure. Le but : reproduire le style "
        "de la playlist dans tes propres productions."
    )
    md.append("")
    md.append(
        "Ce document est destiné à un **beatmaker / producer** qui souhaite "
        "créer une track dans le style de la playlist analysée. Il peut aussi "
        "être donné à un **assistant IA** pour qu'il l'explique, le résume, "
        "ou réponde à des questions concrètes (\"quel BPM viser ?\", \"comment "
        "matcher le volume du master ?\"). Toutes les définitions techniques "
        "sont fournies dans le glossaire ci-dessous."
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Métadonnées
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Métadonnées")
    md.append("")
    md.append("| Champ | Valeur |")
    md.append("|---|---|")
    md.append(f"| Playlist | {playlist_name} |")
    md.append(f"| Date d'analyse | {now} |")
    md.append(f"| Nombre de tracks | {n} |")
    md.append(
        f"| Tracks avec tonalité fiable (vote 3/3) | "
        f"{n_reliable} ({all_agree_pct:.0f}%) |"
    )
    md.append(f"| Version Beatfinder | {__version__} |")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Comment lire ce brief
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Comment lire ce brief")
    md.append("")
    md.append(
        "Les valeurs présentées sont en majorité des **médianes** calculées "
        "sur l'ensemble des tracks, complétées par des écarts-types et des "
        "intervalles interquartiles (`p25-p75`) pour qualifier la dispersion. "
        "La médiane est plus représentative que la moyenne car elle ignore "
        "les outliers."
    )
    md.append("")
    md.append("**Plan du document :**")
    md.append("")
    md.append("1. **TL;DR** — résumé express en 5 lignes pour démarrer")
    md.append(
        "2. **Sections analytiques** (Tempo, Tonalité, Énergie, Spectral, "
        "Structure) — les chiffres mesurés sur la playlist"
    )
    md.append(
        "3. **Sections action** (À copier, À éviter) — règles concrètes "
        "dérivées, à appliquer dans ta DAW"
    )
    md.append(
        "4. **Sections optionnelles** (Sous-clusters, Tracks de référence) — "
        "enrichissements conditionnels selon la playlist"
    )
    md.append(
        "5. **Méthodologie** — comment Beatfinder calcule les chiffres"
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Glossaire
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Glossaire")
    md.append("")
    md.append(
        "*Termes techniques utilisés dans ce brief. À consulter si une "
        "définition manque.*"
    )
    md.append("")
    md.append(
        "- **BPM** (*Beats Per Minute*) : vitesse rythmique. 60 BPM = "
        "1 battement par seconde."
    )
    md.append(
        "- **Onset density** : nombre de débuts de notes détectés par seconde. "
        "Mesure la densité de l'événement rythmique."
    )
    md.append(
        "- **Beat consistency** : régularité de la grille rythmique "
        "(0=très élastique, 1=très régulière, type machine)."
    )
    md.append(
        "- **Mode** : majeur (lumineux) ou mineur (sombre). Caractère "
        "principal de la tonalité."
    )
    md.append(
        "- **Note racine** : fondamentale de la tonalité (C, D, E, F, G, A, "
        "B + dièses/bémols, ex: `F#`)."
    )
    md.append(
        "- **Vote 3/3** : indicateur de fiabilité de la détection de "
        "tonalité — 3 algorithmes votent, 3/3 = très fiable."
    )
    md.append(
        "- **LUFS** (*Loudness Units Full Scale*) : mesure normalisée du "
        "volume perçu (norme broadcast ITU BS.1770-4). Standard streaming : "
        "-14 LUFS. Plus on se rapproche de 0, plus c'est fort."
    )
    md.append(
        "- **True Peak (TP)** : niveau crête en dBFS. 0 dBFS = saturation "
        "théorique. TP > 0 = inter-sample clipping."
    )
    md.append(
        "- **Crest factor** : ratio entre les pics et la moyenne RMS, en dB. "
        "Élevé (>14 dB) = peu compressé, respire ; bas (<8 dB) = compression "
        "marquée."
    )
    md.append(
        "- **DR** (*Dynamic Range*, p95-p10) : écart entre les sections "
        "fortes (drop) et calmes (intro) du track."
    )
    md.append(
        "- **Bandes spectrales** : découpe du spectre audio en 6 zones "
        "fréquentielles — sub (20-60 Hz), bass (60-250 Hz), low-mid "
        "(250-500 Hz), mid (500 Hz - 2 kHz), high-mid (2-6 kHz), high "
        "(6-20 kHz)."
    )
    md.append(
        "- **Centroid** : \"centre de gravité\" du spectre en Hz. Bas = "
        "sombre ; haut = brillant."
    )
    md.append(
        "- **Rolloff 85%** : fréquence sous laquelle 85% de l'énergie "
        "cumulée est concentrée."
    )
    md.append(
        "- **Flatness** : ratio bruit/tonal du spectre. 0 = tonal pur ; "
        "1 = bruit blanc."
    )
    md.append(
        "- **Drop** : moment de plus haute énergie d'un track (souvent "
        "l'entrée du refrain principal)."
    )
    md.append(
        "- **fit_score** : indicateur 0-100% de représentativité d'une "
        "track par rapport à la moyenne de la playlist."
    )
    md.append(
        "- **Sous-cluster** : sous-groupe de tracks aux caractéristiques "
        "distinctes détecté par k-means + silhouette score."
    )
    md.append("")
    md.append("---")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # TL;DR
    # ─────────────────────────────────────────────────────────────────────
    md.append("## TL;DR — session DAW")
    md.append("")
    _intro(
        "Le résumé express : tout ce qu'il te faut savoir avant de lancer "
        "ta DAW. Tempo cible, tonalité majoritaire, volume du master et "
        "structure du drop, en 5 lignes."
    )
    bpm_clusters = _detect_bpm_clusters(tempo.get("bpm_raw") or [])
    if len(bpm_clusters) == 2:
        c1, c2 = bpm_clusters
        md.append(
            f"- **BPM bimodal** : 2 sous-clusters — **{c1[0]:.0f}** "
            f"({c1[1]} tracks) et **{c2[0]:.0f}** ({c2[1]} tracks). "
            "Choisis ton style avant de produire."
        )
    else:
        md.append(
            f"- **BPM cible** : **{bpm_med:.0f}** "
            f"(cluster {bpm_p25:.0f}–{bpm_p75:.0f})"
        )
    root_caveat = (
        f" (sur {root_n_used} tracks vote 3/3)" if root_is_filtered
        else f" (sur {root_n_used} tracks, fiabilité limitée)"
    )
    md.append(
        f"- **Tonalité** : **{minor_pct:.0f}% minor**, racine la plus "
        f"fréquente **{top_root}** ({top_root_pct * 100:.0f}%){root_caveat}"
    )
    md.append(
        f"- **Master** : viser **{lufs_med:.1f} LUFS**, "
        f"TP médian {tp_med:+.1f} dBFS"
    )
    md.append(
        f"- **Profil low-end** : sub {sub_pct:.0f}% + bass {bass_pct:.0f}% = "
        f"**{sub_pct + bass_pct:.0f}% sous 250 Hz**"
    )
    drop_label_tldr, drop_high_var_tldr = _drop_variance_label(
        structure["drop_position_ratio"]
    )
    if drop_high_var_tldr:
        md.append(f"- **Drop** : {drop_label_tldr}")
    else:
        md.append(
            f"- **Drop principal** : à ~{drop_pct:.0f}% du track "
            f"(IQR {structure['drop_position_ratio']['p25'] * 100:.0f}–"
            f"{structure['drop_position_ratio']['p75'] * 100:.0f}%)"
        )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Tempo & rythme
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Tempo & rythme")
    md.append("")
    _intro(
        "À quelle vitesse jouent les tracks et à quel point la grille "
        "rythmique est dense. Le BPM (battements par minute) est la "
        "première décision à prendre. Les autres chiffres disent si la "
        "playlist est plutôt percussive saturée ou aérée."
    )
    md.append(
        f"- **BPM** : médian **{bpm_med:.1f}** ± {tempo['bpm']['std']:.1f}, "
        f"range {tempo['bpm']['min']:.0f}–{tempo['bpm']['max']:.0f}"
    )
    md.append(f"- **Cluster 50%** : {bpm_p25:.0f}–{bpm_p75:.0f} BPM")
    onset_med = tempo["onset_density"]["median"]
    md.append(
        f"- **Onset density** : {onset_med:.1f}/sec — {_interpret_onset(onset_med)}"
    )
    md.append(
        f"- **Beat consistency** : {tempo['beat_consistency']['median']:.2f}/1"
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Tonalité
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Tonalité")
    md.append("")
    _intro(
        "La gamme musicale dominante (Do mineur, La majeur…) sur l'ensemble "
        "des tracks. Mineur = ambiance sombre, majeur = ambiance lumineuse. "
        "Te dit dans quelle clé écrire ta mélodie pour qu'elle sonne "
        "cohérente avec la playlist."
    )
    reliable_tag = " *(votes 3/3)*" if root_is_filtered else ""
    md.append(
        f"- **Racine dominante** : `{top_root}` ({top_root_pct * 100:.0f}%) "
        f"sur {root_n_used}/{n} tracks{reliable_tag}"
    )
    top_3 = list(root_dist.items())[:3]
    if len(top_3) > 1:
        runners = ", ".join(f"`{r}` ({p * 100:.0f}%)" for r, p in top_3[1:])
        md.append(f"- Runners up : {runners}")
    md.append(
        f"- **Mode** : minor {minor_pct:.0f}% / major {100 - minor_pct:.0f}%"
    )
    vote = tonality.get("vote_count", {})
    if vote.get("median") is not None:
        md.append(
            f"- **Fiabilité key** : vote_count médian {vote['median']:.1f}/3, "
            f"accord parfait sur {all_agree_pct:.0f}% des tracks"
        )
    n_mod = tonality["n_modulations"]["median"]
    if n_mod > 0:
        md.append(
            f"- **Modulations intra-track** : {n_mod:.0f} segments 10s — "
            "tracks pas statiques"
        )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Énergie & mastering
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Énergie & mastering")
    md.append("")
    _intro(
        "Volume perçu et dynamique du master final. Le LUFS est le standard "
        "utilisé par les plateformes de streaming (Spotify, YouTube, Apple "
        "Music) pour normaliser le son. Ces chiffres te disent à quel niveau "
        "pousser ton master."
    )
    md.append(
        f"- **LUFS intégré** : médian **{lufs_med:.1f} dB** — "
        f"{_interpret_lufs(lufs_med)}"
    )
    tp_max = energy["true_peak_db"]["max"]
    md.append(
        f"- **True peak** : médian {tp_med:+.1f} dBFS (max {tp_max:+.1f}) — "
        f"{_interpret_tp(tp_med)}"
    )
    md.append(f"- **Crest factor** : {energy['crest_factor_db']['median']:.1f} dB")
    dr = energy["dynamic_range_db"]["median"]
    md.append(f"- **DR (p95-p10)** : {dr:.1f} dB — {_interpret_dr(dr)}")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Profil spectral
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Profil spectral")
    md.append("")
    _intro(
        "Comment l'énergie sonore se répartit du grave à l'aigu (6 bandes). "
        "Te dit si la playlist est plutôt low-end, mid-centric ou aérée — "
        "et le tableau donne une suggestion EQ par bande."
    )
    md.append("| Bande | Plage | Médiane | | Action mix |")
    md.append("|-------|-------|---------|---|-----------|")
    bands = spectral["band_energy"]
    eq_actions = _eq_actions(bands)
    band_info = [
        ("Sub", "20–60 Hz", "sub"),
        ("Bass", "60–250 Hz", "bass"),
        ("Low-mid", "250–500 Hz", "low_mid"),
        ("Mid", "500–2k Hz", "mid"),
        ("High-mid", "2–6k Hz", "high_mid"),
        ("High", "6–20k Hz", "high"),
    ]
    for label, range_, key in band_info:
        v = bands[key]["median"]
        md.append(
            f"| {label} | {range_} | {v * 100:.1f}% | `{_band_bar(v)}` | "
            f"{eq_actions[key]} |"
        )
    md.append("")
    md.append(
        f"- **Centroid** : {spectral['centroid_hz']['median']:.0f} Hz — "
        f"{_interpret_centroid(spectral['centroid_hz']['median'])}"
    )
    md.append(f"- **Rolloff 85%** : {spectral['rolloff85_hz']['median']:.0f} Hz")
    md.append(
        f"- **Flatness** : {spectral['flatness']['median']:.4f} — "
        f"{_interpret_flatness(spectral['flatness']['median'])}"
    )
    md.append(f"- **Signature** : {_spectral_profile_label(bands)}")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Structure
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Structure")
    md.append("")
    _intro(
        "Combien de sections (intro / couplet / drop / pont / outro) dans "
        "une track moyenne, et à quel moment le drop principal tombe. "
        "T'aide à planifier l'architecture de ta track pour qu'elle colle "
        "aux conventions du style."
    )
    md.append(f"- **Sections moyennes** : {structure['n_sections']['median']:.0f}")
    drop_label_struct, drop_high_var_struct = _drop_variance_label(
        structure["drop_position_ratio"]
    )
    if drop_high_var_struct:
        md.append(f"- **Drop position** : {drop_label_struct}")
    else:
        md.append(
            f"- **Drop principal** : à {drop_pct:.0f}% du track "
            f"(~{int(dur_med * drop_pct / 100)}s sur un track de {dur_med:.0f}s) — "
            f"{_interpret_drop(structure['drop_position_ratio']['median'])}"
        )
    md.append(f"- **Durée médiane** : {dur_med:.0f}s")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # À copier
    # ─────────────────────────────────────────────────────────────────────
    md.append("## À copier")
    md.append("")
    _intro(
        "Les patterns que tu peux directement reproduire sur ta prod : "
        "ce qui marche statistiquement dans cette playlist. Règles "
        "concrètes type \"sub à 25%\", \"BPM autour de 130\", \"drop avant 30%\"."
    )
    for b in _to_copy(pattern):
        md.append(f"- {b}")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # À éviter
    # ─────────────────────────────────────────────────────────────────────
    md.append("## À éviter")
    md.append("")
    _intro(
        "Les pièges identifiés : ce qui ferait sortir ta track du style de "
        "la playlist. Règles inverses type \"ne pas dépasser -8 LUFS\", "
        "\"éviter plus de 70% de sub\"."
    )
    for b in _to_avoid(pattern):
        md.append(f"- {b}")
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Sous-clusters détectés par k-means (si silhouette suffisante)
    # ─────────────────────────────────────────────────────────────────────
    subclusters = pattern.get("subclusters")
    if subclusters and subclusters.get("clusters"):
        md.append("## Sous-clusters détectés")
        md.append("")
        _intro(
            "Si la playlist mélange plusieurs sous-styles (par ex. tempos "
            "rapides + tempos lents, ou productions sombres + productions "
            "lumineuses), cette section les sépare. Chaque cluster a ses "
            "propres médianes et ses tracks. Choisis le cluster cible avant "
            "de produire."
        )
        md.append(
            f"_{subclusters['n_clusters']} sous-clusters identifiés "
            f"(silhouette {subclusters['silhouette']:.2f}, "
            f"sur {subclusters['n_tracks_used']}/{n} tracks). "
            "La playlist mélange plusieurs sous-styles — choisis ton "
            "cluster cible avant de produire._"
        )
        md.append("")
        for ci, cluster in enumerate(subclusters["clusters"], 1):
            med = cluster["medians"]
            md.append(
                f"### Cluster {ci} — {cluster['size']} tracks "
                f"(BPM {med['bpm']:.0f}, LUFS {med['lufs']:+.1f})"
            )
            md.append("")
            md.append(
                f"- DR {med['dr']:.1f} dB / Crest {med['crest']:.1f} dB"
            )
            md.append(
                f"- Sub {med['sub'] * 100:.0f}% / Bass {med['bass'] * 100:.0f}% / "
                f"Mid {med['mid'] * 100:.0f}% / High-mid {med['high_mid'] * 100:.0f}%"
            )
            md.append(
                f"- Centroid {med['centroid']:.0f} Hz, drop à {med['drop'] * 100:.0f}%"
            )
            if tracks_data:
                artist_count: Counter[str] = Counter()
                for idx in cluster["track_indices"]:
                    if 0 <= idx < len(tracks_data):
                        primary = (
                            tracks_data[idx].get("artist") or "?"
                        ).split(",")[0].strip()
                        artist_count[primary] += 1
                top_artists = ", ".join(
                    f"{a} ({c})" for a, c in artist_count.most_common(4)
                )
                if top_artists:
                    md.append(f"- Top artistes : {top_artists}")
            md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Tracks de référence (top fit_score)
    # ─────────────────────────────────────────────────────────────────────
    if tracks_data:
        scored = [
            {**t, "fit": _fit_score(t.get("features"), pattern)}
            for t in tracks_data
        ]
        scored.sort(
            key=lambda x: (x["fit"] if x["fit"] is not None else -1),
            reverse=True,
        )
        total = len(scored)
        truncated = total > 35
        top_rows = scored[:30] if truncated else scored
        bottom_rows = scored[-5:] if truncated else []

        # Marker HTML pour forcer un page break PDF avant cette section
        # (les styles print injectent `break-before: page` sur cette classe).
        md.append('<div class="brief-tracks-ref-break"></div>')
        md.append("")
        md.append("## Tracks de référence (triées par fit_score)")
        md.append("")
        _intro(
            "Les tracks les plus représentatives de la playlist, triées par "
            "fit_score (à quel point chaque track colle à la moyenne du "
            "groupe). Écoute les premières en priorité comme références."
        )
        if truncated:
            md.append(
                f"_fit_score = % de features de la track dans le p25-p75 "
                f"de la playlist. Affichage Top 30 + Bottom 5 sur {total} "
                "tracks au total — voir le CSV complet pour la liste "
                "exhaustive._"
            )
        else:
            md.append(
                "_fit_score = % de features de la track dans le p25-p75 de "
                "la playlist. Les top tracks sont les plus représentatives "
                "à écouter en priorité comme référence._"
            )
        md.append("")
        md.append(
            "| # | Fit | Artist | Title | BPM | Key | V | LUFS | Sub+Bass | Drop% |"
        )
        md.append(
            "|---|-----|--------|-------|-----|-----|---|------|----------|-------|"
        )

        def _format_row(idx: int, t: dict) -> str:
            f = t.get("features") or {}
            tempo_f = f.get("tempo") or {}
            ton_f = f.get("tonality") or {}
            energy_f = f.get("energy") or {}
            band_f = (f.get("spectral") or {}).get("band_energy") or {}
            struct_f = f.get("structure") or {}
            sb = ((band_f.get("sub") or 0) + (band_f.get("bass") or 0)) * 100
            lufs = energy_f.get("lufs_integrated")
            lufs_str = f"{lufs:+.1f}" if lufs is not None else "—"
            fit = t.get("fit")
            fit_str = f"{fit * 100:.0f}%" if fit is not None else "—"
            return (
                f"| {idx} | {fit_str} | {(t.get('artist') or '?')[:20]} | "
                f"{(t.get('title') or '?')[:25]} | "
                f"{tempo_f.get('bpm', 0):.0f} | "
                f"{ton_f.get('key', '?')} | "
                f"{ton_f.get('vote_count', 0)}/3 | "
                f"{lufs_str} | "
                f"{sb:.0f}% | "
                f"{(struct_f.get('drop_position_ratio') or 0) * 100:.0f}% |"
            )

        for i, t in enumerate(top_rows, 1):
            md.append(_format_row(i, t))
        if bottom_rows:
            md.append("| ⋯ | | | | | | | | | |")
            for offset, t in enumerate(bottom_rows):
                md.append(_format_row(total - len(bottom_rows) + offset + 1, t))
        md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Méthodologie
    # ─────────────────────────────────────────────────────────────────────
    md.append("## Méthodologie")
    md.append("")
    _intro(
        "Comment Beatfinder calcule les chiffres ci-dessus. À lire si tu "
        "veux comprendre la méthode (analyseurs audio utilisés, consensus "
        "de votes pour la tonalité…) ou si certains résultats te semblent "
        "louches."
    )
    md.append(
        "- **Pipeline** : Spotify Web API → YouTube (yt-dlp) → "
        "librosa + pyloudnorm + madmom CNN."
    )
    md.append(
        "- **Tonalité** : consensus 3 voters (KS chroma_cens, KS chroma_cqt, "
        "madmom). Le top-root est calculé sur les tracks vote 3/3 "
        "uniquement (filtrage fiabilité). Plafond ~60% root sur les "
        "musiques avec voix très traitée (autotune) et basses synthétiques "
        "tonales."
    )
    md.append(
        "- **BPM** : `librosa.beat.beat_track` + correction anti-octave-error. "
        "Bimodalité détectée via gap analysis (IQR > 25 BPM)."
    )
    md.append(
        "- **fit_score** : % de features de la track dans le p25-p75 de la "
        "playlist, pondéré (BPM + LUFS + bandes spectrales + drop)."
    )
    md.append(
        "- **Sous-clusters** : k-means + silhouette score > 0.10 sur features "
        "clés (BPM, LUFS, DR, crest, bandes spectrales, drop, centroid). "
        "Seuil bas car les playlists varient souvent en continuum stylistique "
        "plutôt qu'en groupes nets. None = playlist homogène."
    )
    md.append(
        "- **DR p95-p10** : capture le contraste macro (intro/drop), pas la "
        "compression locale. Pour la compression réelle, regarder "
        "`crest_factor_db`."
    )
    md.append("")

    # ─────────────────────────────────────────────────────────────────────
    # Footer
    # ─────────────────────────────────────────────────────────────────────
    md.append("---")
    md.append("")
    md.append(
        f"*Brief généré par Beatfinder v{__version__} le {now}.*"
    )
    md.append("")

    return "\n".join(md)
