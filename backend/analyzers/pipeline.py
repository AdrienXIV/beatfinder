"""Pipeline d'analyse complète d'un track audio.

`analyze_track(path, on_step, on_log)` charge le MP3 une fois et fait passer
tous les analyzers V1 (tempo, tonality, energy, spectral, structure, timbre).
Sortie prête à JSON-serializer.

Ordre interne optimisé : tonality avant structure pour bénéficier du cache HPSS.

Les callbacks `on_step` et `on_log` permettent à la UI d'afficher une
progression fluide (fraction entre 0 et 1) et un log textuel détaillé.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Final

from backend.types import LogCallback, StepCallback

from . import _loader, energy, spectral, structure, tempo, timbre, tonality

# Liste ordonnée des étapes pour le reporting de progression.
ANALYZE_STEPS: Final[list[tuple[str, str]]] = [
    ("load", "Chargement audio"),
    ("tempo", "Tempo & rythme"),
    ("tonality", "Tonalité (3 voters)"),
    ("energy", "Énergie & mastering"),
    ("spectral", "Profil spectral"),
    ("structure", "Structure / drop"),
    ("timbre", "Timbre (MFCC)"),
]


def analyze_track(
    path: Path | str,
    on_step: StepCallback | None = None,
    on_log: LogCallback | None = None,
) -> dict:
    """Charge l'audio + run les 6 analyzers. Retourne un dict prêt JSON.

    `on_step(step_key, step_label, fraction)` est appelé 2× par étape (avant et
    après la computation) avec `fraction` ∈ [0, 1] (proportion du track terminée).
    Permet à la UI d'animer la progression entre les étapes.

    `on_log(message)` est appelé pour les sous-étapes textuelles (start, done,
    métriques produites). Vide-grenier qui rend visible la complexité du pipeline.
    """
    n_steps = len(ANALYZE_STEPS)

    def step(idx: int, sub: str) -> None:
        if on_step is None:
            return
        key, label = ANALYZE_STEPS[idx]
        fraction = (idx + (1.0 if sub == "done" else 0.0)) / n_steps
        on_step(key, label, fraction)

    def log(msg: str) -> None:
        if on_log is not None:
            on_log(msg)
            # Petit espacement (~80 ms) après les sous-logs `→` pour donner du
            # rythme à la UI : sinon plusieurs lignes apparaissent en bloc quand
            # les opérations sont rapides (load audio, MFCC, …). Le `→` est notre
            # signal "en cours". Les `✓` finissent l'étape, pas de sleep.
            if msg.lstrip().startswith("→"):
                time.sleep(0.08)

    p = Path(path)

    # 0. Chargement audio
    step(0, "start")
    log("  → chargement audio (librosa.load, mono, sr=22050)")
    t0 = time.perf_counter()
    bundle = _loader.load_audio(p)
    dt = time.perf_counter() - t0
    log(
        f"  ✓ {bundle.duration_sec:.1f}s @ {bundle.sr} Hz "
        f"({len(bundle.y)} samples, {dt * 1000:.0f} ms)"
    )
    step(0, "done")

    # 1. Tempo & rythme
    step(1, "start")
    log("  → beat tracking : librosa.beat.beat_track + onset_detect")
    log("  → correction anti-octave-error (multiples de 2/3)")
    t0 = time.perf_counter()
    tempo_data = tempo.analyze(bundle).as_dict()
    dt = time.perf_counter() - t0
    bpm = tempo_data.get("bpm", 0) or 0
    onset = tempo_data.get("onset_density", 0) or 0
    beat_c = tempo_data.get("beat_consistency", 0) or 0
    log(
        f"  ✓ BPM={bpm:.1f} · onset_density={onset:.2f}/s · "
        f"beat_consistency={beat_c:.2f} ({dt:.1f}s)"
    )
    step(1, "done")

    # 2. Tonalité (3 voters)
    step(2, "start")
    log("  → Krumhansl-Schmuckler #1 : chroma_cens (librosa)")
    log("  → Krumhansl-Schmuckler #2 : chroma_cqt (librosa)")
    log("  → madmom CNN inference (CNNKeyRecognitionProcessor)")
    log("  → consensus 3 voters + uncertainty score")
    t0 = time.perf_counter()
    tonality_data = tonality.analyze(bundle).as_dict()
    dt = time.perf_counter() - t0
    note = tonality_data.get("note", "?")
    mode = tonality_data.get("mode", "?")
    vc = tonality_data.get("vote_count", 0) or 0
    log(
        f"  ✓ key={note} {mode} · vote={vc}/3 · "
        f"{'agreement_full' if tonality_data.get('methods_agree_all') else 'partial'} "
        f"({dt:.1f}s)"
    )
    step(2, "done")

    # 3. Énergie & mastering
    step(3, "start")
    log("  → RMS frame-wise + agrégation médiane")
    log("  → LUFS intégré (pyloudnorm, BS.1770-4)")
    log("  → true peak (4× oversampling)")
    log("  → crest factor + dynamic range (p95-p10)")
    t0 = time.perf_counter()
    energy_data = energy.analyze(bundle).as_dict()
    dt = time.perf_counter() - t0
    lufs = energy_data.get("lufs_integrated", 0) or 0
    tp = energy_data.get("true_peak_db", 0) or 0
    crest = energy_data.get("crest_factor_db", 0) or 0
    dr = energy_data.get("dynamic_range_db", 0) or 0
    log(
        f"  ✓ LUFS={lufs:+.1f} dB · TP={tp:+.1f} dBFS · "
        f"crest={crest:.1f} dB · DR={dr:.1f} dB ({dt:.1f}s)"
    )
    step(3, "done")

    # 4. Profil spectral
    step(4, "start")
    log("  → STFT n_fft=2048, hop=512")
    log("  → spectral centroid + rolloff 85% + flatness")
    log("  → découpe en 6 bandes : sub/bass/low_mid/mid/high_mid/high")
    t0 = time.perf_counter()
    spectral_data = spectral.analyze(bundle).as_dict()
    dt = time.perf_counter() - t0
    cen = spectral_data.get("centroid_hz", 0) or 0
    rolloff = spectral_data.get("rolloff85_hz", 0) or 0
    be = spectral_data.get("band_energy", {}) or {}
    sub_pct = (be.get("sub", 0) or 0) * 100
    bass_pct = (be.get("bass", 0) or 0) * 100
    log(
        f"  ✓ centroid={cen:.0f} Hz · rolloff85={rolloff:.0f} Hz · "
        f"sub={sub_pct:.0f}% · bass={bass_pct:.0f}% ({dt:.1f}s)"
    )
    step(4, "done")

    # 5. Structure / drop
    step(5, "start")
    log("  → HPSS (harmonic-percussive separation)")
    log("  → novelty curve sur self-similarity matrix")
    log("  → segment detection + drop position estimate")
    t0 = time.perf_counter()
    structure_data = structure.analyze(bundle).as_dict()
    dt = time.perf_counter() - t0
    nseg = structure_data.get("n_sections", 0) or 0
    drop = (structure_data.get("drop_position_ratio", 0) or 0) * 100
    log(f"  ✓ {nseg} sections · drop@{drop:.0f}% du track ({dt:.1f}s)")
    step(5, "done")

    # 6. Timbre (MFCC)
    step(6, "start")
    log("  → MFCC 13 coefficients (librosa.feature.mfcc)")
    log("  → agrégation temporelle (mean + std)")
    t0 = time.perf_counter()
    timbre_data = timbre.analyze(bundle).as_dict()
    dt = time.perf_counter() - t0
    log(f"  ✓ MFCC mean+std computed ({dt:.1f}s)")
    step(6, "done")

    return {
        "duration_sec": round(bundle.duration_sec, 2),
        "sr": bundle.sr,
        "tempo": tempo_data,
        "tonality": tonality_data,
        "energy": energy_data,
        "spectral": spectral_data,
        "structure": structure_data,
        "timbre": timbre_data,
    }
