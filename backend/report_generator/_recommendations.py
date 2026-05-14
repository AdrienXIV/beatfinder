"""Génération des bullets "À copier" / "À éviter" + actions EQ par bande."""
from __future__ import annotations

from ._analytics import _drop_variance_label, _root_dist_and_n
from ._helpers import _interpret_drop, _interpret_lufs, _interpret_onset


def _eq_actions(bands: dict) -> dict[str, str]:
    """Conseils action par bande, dépendants de l'énergie médiane mesurée.

    Les conseils sont écrits pour un beatmaker FL Studio : action FR, conditionnel
    sur les seuils observés.
    """
    sub = bands["sub"]["median"]
    bass = bands["bass"]["median"]
    low_mid = bands["low_mid"]["median"]
    mid = bands["mid"]["median"]
    high_mid = bands["high_mid"]["median"]
    high = bands["high"]["median"]
    return {
        "sub": (
            "sub-bass long et tonal, vise fondamental ~50 Hz" if sub > 0.30
            else "sub présent mais discret" if sub > 0.15
            else "sub léger, kick acoustique probable"
        ),
        "bass": (
            "kick + sub vrombissant, zone 60–250 Hz dominante" if bass > 0.30
            else "bass équilibrée, ne sature pas la zone kick" if bass > 0.20
            else "bass minimale, mix orienté mid/high"
        ),
        "low_mid": (
            "zone trop chargée → boue probable, low-cut 200 Hz sur tout sauf kick/sub" if low_mid > 0.20
            else "creux 250–500 Hz typique, laisse cette zone fine"
        ),
        "mid": (
            "voix très exposée, mix sec et frontal" if mid > 0.20
            else "voix dans la moyenne, headroom mid OK" if mid > 0.10
            else "voix discrète, ambient/instrumental dominant"
        ),
        "high_mid": (
            "présence/sibilance forte → de-esser obligatoire" if high_mid > 0.10
            else "boost +2 dB à 4 kHz si voix manque de mordant" if high_mid > 0.03
            else "high-mid étouffé (rolloff agressif)"
        ),
        "high": (
            "hats/cymbales brillants, air généreux" if high > 0.05
            else "hats discrets, low-pass 8–10 kHz typique"
        ),
    }


def _to_copy(pattern: dict) -> list[str]:
    tempo = pattern["tempo"]
    energy = pattern["energy"]
    spectral = pattern["spectral"]
    structure = pattern["structure"]
    tonality = pattern["tonality"]
    bullets: list[str] = []

    bpm_med = tempo["bpm"]["median"]
    bullets.append(
        f"BPM cible **{bpm_med:.0f}**, cluster typique "
        f"**{tempo['bpm']['p25']:.0f}–{tempo['bpm']['p75']:.0f}**"
    )

    mode_dist = tonality["mode"]["distribution"]
    minor_pct = mode_dist.get("minor", 0) * 100
    if minor_pct > 65:
        bullets.append(f"Reste en **mineur** ({minor_pct:.0f}% des tracks de réf)")
    elif minor_pct < 35:
        bullets.append(f"Vise **majeur** ({100 - minor_pct:.0f}% des tracks de réf)")

    root_dist, root_n_used, root_is_filtered = _root_dist_and_n(tonality)
    if root_dist:
        top_3 = list(root_dist.items())[:3]
        roots_str = ", ".join(f"**{r}** ({p * 100:.0f}%)" for r, p in top_3)
        caveat = (
            f" (sur {root_n_used} tracks vote 3/3)" if root_is_filtered
            else f" (sur {root_n_used} tracks, fiabilité limitée)"
        )
        bullets.append(f"Note racine probable, dans l'ordre : {roots_str}{caveat}")

    lufs_med = energy["lufs_integrated"]["median"]
    bullets.append(
        f"Master à **{lufs_med:.1f} LUFS** — {_interpret_lufs(lufs_med)}"
    )

    tp_med = energy["true_peak_db"]["median"]
    if tp_med > 0:
        bullets.append(
            f"Accepte l'inter-sample clipping (TP médian {tp_med:+.1f} dBFS) "
            "pour pousser le LUFS au niveau de la playlist"
        )

    sub_pct = spectral["band_energy"]["sub"]["median"] * 100
    bass_pct = spectral["band_energy"]["bass"]["median"] * 100
    bullets.append(
        f"Sub-bass massif : **{sub_pct:.0f}%** de l'énergie sous 60 Hz (basses longues et tonales)"
    )
    bullets.append(
        f"Bass dominante : **{bass_pct:.0f}%** entre 60-250 Hz (kick + sub vrombissant)"
    )

    drop_label, drop_high_var = _drop_variance_label(structure["drop_position_ratio"])
    if not drop_high_var:
        drop_pct = structure["drop_position_ratio"]["median"] * 100
        bullets.append(
            f"Drop principal à **~{drop_pct:.0f}% du track** "
            f"— {_interpret_drop(structure['drop_position_ratio']['median'])}"
        )
    else:
        bullets.append(
            f"Position du drop **non recommandée comme cible** — {drop_label}"
        )

    od = tempo["onset_density"]["median"]
    bullets.append(f"Rythme **{od:.1f} onsets/sec** — {_interpret_onset(od)}")

    return bullets


def _to_avoid(pattern: dict) -> list[str]:
    tempo = pattern["tempo"]
    energy = pattern["energy"]
    spectral = pattern["spectral"]
    tonality = pattern["tonality"]
    bullets: list[str] = []

    bpm_min = tempo["bpm"]["min"]
    bpm_max = tempo["bpm"]["max"]
    bpm_med = tempo["bpm"]["median"]
    bpm_std = tempo["bpm"]["std"]
    if bpm_max - bpm_min > 50 or bpm_std > 20:
        bullets.append(
            f"BPM hors zone **{bpm_med - bpm_std:.0f}–{bpm_med + bpm_std:.0f}** "
            f"(±1σ autour de la médiane) — range complet {bpm_min:.0f}–{bpm_max:.0f}, "
            f"playlist hétérogène, vérifie le sous-cluster que tu vises"
        )

    mode_dist = tonality["mode"]["distribution"]
    minor_pct = mode_dist.get("minor", 0) * 100
    if minor_pct >= 85:
        bullets.append(
            f"**Majeur** : très rare ({100 - minor_pct:.0f}% des tracks) — sonnera atypique"
        )
    elif minor_pct <= 15:
        bullets.append(
            f"**Mineur** : très rare ({minor_pct:.0f}%) — sonnera atypique"
        )

    mid_pct = spectral["band_energy"]["mid"]["median"] * 100
    if mid_pct > 20:
        bullets.append(
            f"Trop de **mid (500-2k Hz)** : la voix masque le bas (médian {mid_pct:.0f}%)"
        )

    high_pct = spectral["band_energy"]["high"]["median"] * 100
    high_mid_pct = spectral["band_energy"]["high_mid"]["median"] * 100
    top_total = high_pct + high_mid_pct
    if top_total < 10:
        bullets.append(
            f"**Top-end > 10%** atypique — hats/cymbales discrets dans cette playlist "
            f"({top_total:.1f}% médian)"
        )

    lufs_med = energy["lufs_integrated"]["median"]
    if lufs_med > -14:
        bullets.append(
            f"**Master < -16 LUFS** sera perçu comme calme à côté de cette playlist "
            f"(qui tape à {lufs_med:.1f})"
        )

    crest = energy["crest_factor_db"]["median"]
    if crest < 10:
        bullets.append(
            f"Compression molle (crest > 14 dB) — la playlist écrase à {crest:.1f} dB"
        )

    return bullets
