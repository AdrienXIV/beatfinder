"""Valide la cohérence du pipeline d'analyse audio.

Prend un MP3/WAV de référence, applique N transforms connus (gain ±X dB,
pitch shift, time-stretch, low-pass), ré-analyse chaque variante via le vrai
pipeline `analyze_track`, et compare les features attendues vs mesurées.

Usage :
    python -m backend.cli.validate_pipeline <audio.mp3> [--duration 30]

Si le pipeline répond juste, tous les checks doivent passer dans la tolérance
définie. Un FAIL signale un bug dans un analyzer (calibration LUFS, détection
BPM, etc.).
"""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

from backend.analyzers import analyze_track

logging.basicConfig(level=logging.WARNING, format="%(message)s")
log = logging.getLogger("validate_pipeline")

# Demi-tons → notes (cycle chromatique). Pour calcul du shift attendu de la note.
NOTES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def _note_index(note: str | None) -> int | None:
    if not note:
        return None
    if note in NOTES_SHARP:
        return NOTES_SHARP.index(note)
    if note in NOTES_FLAT:
        return NOTES_FLAT.index(note)
    return None


def _shift_note(note: str | None, semitones: int) -> str | None:
    idx = _note_index(note)
    if idx is None:
        return None
    return NOTES_SHARP[(idx + semitones) % 12]


# ─── Catalogue des transforms ─────────────────────────────────────────────


@dataclass
class CheckSpec:
    """Une vérification : feature à comparer + delta attendu + tolérance."""

    label: str
    path: tuple[str, ...]
    kind: str  # "delta" | "ratio" | "note_shift"
    expected: float | int
    tol: float
    unit: str = ""


@dataclass
class TransformSpec:
    """Une transformation à appliquer à l'audio + ses checks."""

    key: str
    label: str
    apply: Callable[[np.ndarray, int], np.ndarray]
    checks: list[CheckSpec] = field(default_factory=list)


# Transforms appliqués
def _gain(y: np.ndarray, sr: int, db: float) -> np.ndarray:
    return y * (10 ** (db / 20.0))


def _time_stretch(y: np.ndarray, sr: int, rate: float) -> np.ndarray:
    return librosa.effects.time_stretch(y=y, rate=rate)


def _pitch_shift(y: np.ndarray, sr: int, n_steps: int) -> np.ndarray:
    return librosa.effects.pitch_shift(y=y, sr=sr, n_steps=n_steps)


def _low_pass(y: np.ndarray, sr: int, fc: int) -> np.ndarray:
    sos = butter(4, fc, btype="low", fs=sr, output="sos")
    return sosfiltfilt(sos, y).astype(np.float32)


def _compressor(y: np.ndarray, sr: int, threshold_db: float, ratio: float) -> np.ndarray:
    """Compresseur instantané (pas d'attack/release) downward.

    Pour chaque échantillon |x| > threshold, on applique :
        y = sign(x) * (threshold + (|x| - threshold) / ratio)

    Effet : peaks écrasés → crest factor baisse car ratio peak/rms diminue.
    """
    threshold = 10 ** (threshold_db / 20.0)
    abs_y = np.abs(y)
    sign = np.sign(y)
    over = abs_y > threshold
    abs_out = np.where(
        over,
        threshold + (abs_y - threshold) / ratio,
        abs_y,
    )
    return (sign * abs_out).astype(np.float32)


def _heavy_compressor(y: np.ndarray, sr: int) -> np.ndarray:
    """Compresseur agressif (8:1 à -30 dB) + makeup gain.

    À la différence du brickwall limiter (qui écrase juste les peaks
    instantanés et baisse le crest), celui-ci compresse aussi les sections
    RMS fortes → aplatit la macro-dynamique → fait baisser DR (p95-p10).
    """
    y_comp = _compressor(y, sr, threshold_db=-30.0, ratio=8.0)
    # Makeup gain pour ramener le peak au niveau original
    src_peak = float(np.max(np.abs(y))) or 1e-9
    new_peak = float(np.max(np.abs(y_comp))) or 1e-9
    return (y_comp * (src_peak / new_peak)).astype(np.float32)


def _boost_band(
    y: np.ndarray, sr: int, low_hz: float, high_hz: float, gain_db: float,
) -> np.ndarray:
    """Boost une bande de fréquences par +gain_db (bandpass + somme pondérée).

    Effet : `band_energy[band_label]` augmente proportionnellement.
    """
    nyq = sr / 2.0
    high = min(high_hz, nyq * 0.99)  # évite Wn=1.0 qui crash butter
    sos = butter(4, [low_hz, high], btype="band", fs=sr, output="sos")
    band = sosfiltfilt(sos, y).astype(np.float32)
    # Gain relatif : on rajoute (G-1) × bande au signal (G=1 → identité)
    extra = (10 ** (gain_db / 20.0)) - 1.0
    return (y + extra * band).astype(np.float32)


TRANSFORMS: list[TransformSpec] = [
    TransformSpec(
        key="gain_minus_3",
        label="Gain -3 dB",
        apply=lambda y, sr: _gain(y, sr, -3.0),
        checks=[
            CheckSpec("LUFS intégré", ("energy", "lufs_integrated"), "delta", -3.0, 0.7, "dB"),
            CheckSpec("True peak", ("energy", "true_peak_db"), "delta", -3.0, 0.7, "dB"),
        ],
    ),
    TransformSpec(
        key="gain_plus_6",
        label="Gain +6 dB",
        apply=lambda y, sr: _gain(y, sr, 6.0),
        checks=[
            CheckSpec("LUFS intégré", ("energy", "lufs_integrated"), "delta", 6.0, 0.7, "dB"),
            CheckSpec("True peak", ("energy", "true_peak_db"), "delta", 6.0, 0.7, "dB"),
        ],
    ),
    TransformSpec(
        key="tempo_x1_1",
        label="Time-stretch ×1.1 (BPM +10%)",
        apply=lambda y, sr: _time_stretch(y, sr, 1.1),
        checks=[
            # ratio_with_harmonics : tolère bascule sur ×2/×0.5/×1.5/×0.75
            # car le détecteur BPM peut choisir un harmonique cohérent
            # (comportement géré en prod par bpm_alt_hypotheses + correction manuelle).
            CheckSpec("BPM (ratio)", ("tempo", "bpm"), "ratio_with_harmonics", 1.10, 0.08, "×"),
        ],
    ),
    TransformSpec(
        key="pitch_plus_2",
        label="Pitch shift +2 demi-tons",
        apply=lambda y, sr: _pitch_shift(y, sr, 2),
        checks=[
            CheckSpec("Note (shift)", ("tonality", "note"), "note_shift", 2, 0, ""),
        ],
    ),
    TransformSpec(
        key="lowpass_5k",
        label="Low-pass 5 kHz (coupe les aigus)",
        apply=lambda y, sr: _low_pass(y, sr, 5000),
        checks=[
            # Centroid doit baisser nettement (énergie haute coupée)
            CheckSpec("Centroid", ("spectral", "centroid_hz"), "delta_negative", -500, 0, "Hz"),
            # Bande "high" doit s'effondrer (>50% de baisse relative)
            CheckSpec(
                "High band (5-20kHz)",
                ("spectral", "band_energy", "high"),
                "ratio_max", 0.3, 0, "%",  # mutated/baseline < 0.3 (=baisse de 70%+)
            ),
        ],
    ),
    TransformSpec(
        key="compressor_4to1",
        label="Compresseur 4:1 à -20 dB (réduction crest factor)",
        apply=lambda y, sr: _compressor(y, sr, threshold_db=-20.0, ratio=4.0),
        checks=[
            # Crest = peak/RMS. Compresser les peaks → crest baisse de ≥1.5 dB
            CheckSpec(
                "Crest factor", ("energy", "crest_factor_db"),
                "delta_negative", -1.5, 0, "dB",
            ),
        ],
    ),
    TransformSpec(
        key="heavy_compressor",
        label="Compresseur agressif 8:1 à -30 dB (réduction dynamic range)",
        apply=_heavy_compressor,
        checks=[
            # Compression macro → aplatit les sections RMS → DR baisse de ≥1 dB
            CheckSpec(
                "Dynamic range", ("energy", "dynamic_range_db"),
                "delta_negative", -1.0, 0, "dB",
            ),
        ],
    ),
    TransformSpec(
        key="boost_sub_12db",
        label="Boost Sub +12 dB (20-60 Hz)",
        apply=lambda y, sr: _boost_band(y, sr, 20, 60, 12.0),
        checks=[
            # La bande sub doit augmenter. Skip si baseline trop faible
            # (audio sans contenu sub → booster du néant donne du néant).
            CheckSpec(
                "Sub band (20-60Hz)", ("spectral", "band_energy", "sub"),
                "delta_positive_if_present", 0.01, 0, "%",
            ),
        ],
    ),
    TransformSpec(
        key="boost_bass_12db",
        label="Boost Bass +12 dB (60-250 Hz)",
        apply=lambda y, sr: _boost_band(y, sr, 60, 250, 12.0),
        checks=[
            CheckSpec(
                "Bass band (60-250Hz)", ("spectral", "band_energy", "bass"),
                "delta_positive", 0.05, 0, "%",
            ),
        ],
    ),
    TransformSpec(
        key="boost_mid_12db",
        label="Boost Mid +12 dB (500-2000 Hz)",
        apply=lambda y, sr: _boost_band(y, sr, 500, 2000, 12.0),
        checks=[
            CheckSpec(
                "Mid band (500-2kHz)", ("spectral", "band_energy", "mid"),
                "delta_positive", 0.05, 0, "%",
            ),
        ],
    ),
    TransformSpec(
        key="pitch_minus_3_preserve_mode",
        label="Pitch shift -3 demi-tons (mode doit être préservé)",
        apply=lambda y, sr: _pitch_shift(y, sr, -3),
        checks=[
            # Un shift chromatique préserve le mode major/minor
            CheckSpec("Mode (préservé)", ("tonality", "mode"), "categorical_same", 0, 0, ""),
        ],
    ),
]


# ─── Helpers d'évaluation ─────────────────────────────────────────────────


def _walk(features: dict, path: tuple[str, ...]) -> Any:
    v: Any = features
    for p in path:
        if not isinstance(v, dict):
            return None
        v = v.get(p)
        if v is None:
            return None
    return v


@dataclass
class CheckResult:
    label: str
    expected: str
    measured: str
    ok: bool
    detail: str = ""


def _format_num(v: float | None, unit: str, decimals: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:.{decimals}f}{unit}"


def evaluate_check(check: CheckSpec, baseline: dict, mutated: dict) -> CheckResult:
    """Calcule attendu vs mesuré et retourne ok/ko."""
    b_raw = _walk(baseline, check.path)
    m_raw = _walk(mutated, check.path)

    if check.kind == "delta":
        if b_raw is None or m_raw is None:
            return CheckResult(check.label, f"Δ {check.expected:+.1f}{check.unit}", "—", False, "valeur absente")
        delta = float(m_raw) - float(b_raw)
        ok = abs(delta - float(check.expected)) <= check.tol
        return CheckResult(
            check.label,
            f"Δ {check.expected:+.1f} {check.unit} (±{check.tol})",
            f"Δ {delta:+.2f} {check.unit} (baseline {b_raw:.2f}, mutated {m_raw:.2f})",
            ok,
        )

    if check.kind == "ratio":
        if b_raw is None or m_raw is None or b_raw == 0:
            return CheckResult(check.label, f"× {check.expected:.2f}", "—", False, "valeur absente")
        ratio = float(m_raw) / float(b_raw)
        ok = abs(ratio - float(check.expected)) <= check.tol
        return CheckResult(
            check.label,
            f"× {check.expected:.2f} (±{check.tol})",
            f"× {ratio:.3f} (baseline {b_raw:.1f}, mutated {m_raw:.1f})",
            ok,
        )

    if check.kind == "ratio_with_harmonics":
        # Cas BPM : le détecteur peut basculer sur un harmonique cohérent
        # (×2, /2, ×1.5, /1.5) à cause de la complexité rythmique du contenu.
        # On accepte si le ratio match l'expected OU l'un de ses harmoniques.
        if b_raw is None or m_raw is None or b_raw == 0:
            return CheckResult(check.label, f"× {check.expected:.2f}", "—", False, "valeur absente")
        ratio = float(m_raw) / float(b_raw)
        target = float(check.expected)
        harmonics = [target, target * 2, target / 2, target * 1.5, target / 1.5,
                     target * 0.75, target / 0.75]
        best_h = min(harmonics, key=lambda h: abs(ratio - h))
        ok = abs(ratio - best_h) <= check.tol
        harmonic_note = (
            "" if abs(best_h - target) < 0.01
            else f" [bascule harmonique ×{best_h / target:.2f}]"
        )
        return CheckResult(
            check.label,
            f"× {check.expected:.2f} (±{check.tol}, harmoniques OK)",
            f"× {ratio:.3f} (baseline {b_raw:.1f}, mutated {m_raw:.1f}){harmonic_note}",
            ok,
        )

    if check.kind == "delta_negative":
        # Vérifie juste que la baisse est au moins de `expected` (négatif).
        if b_raw is None or m_raw is None:
            return CheckResult(check.label, f"Δ ≤ {check.expected:+.1f}{check.unit}", "—", False, "valeur absente")
        delta = float(m_raw) - float(b_raw)
        ok = delta <= float(check.expected)
        return CheckResult(
            check.label,
            f"Δ ≤ {check.expected:+.1f} {check.unit}",
            f"Δ {delta:+.2f} {check.unit} (baseline {b_raw:.2f}, mutated {m_raw:.2f})",
            ok,
        )

    if check.kind == "delta_positive":
        # Vérifie qu'une augmentation d'au moins `expected` est mesurée.
        if b_raw is None or m_raw is None:
            return CheckResult(check.label, f"Δ ≥ {check.expected:+.2f}{check.unit}", "—", False, "valeur absente")
        delta = float(m_raw) - float(b_raw)
        ok = delta >= float(check.expected)
        b_disp = float(b_raw) * 100 if "%" in check.unit else float(b_raw)
        m_disp = float(m_raw) * 100 if "%" in check.unit else float(m_raw)
        d_disp = delta * 100 if "%" in check.unit else delta
        exp_disp = float(check.expected) * 100 if "%" in check.unit else float(check.expected)
        return CheckResult(
            check.label,
            f"Δ ≥ {exp_disp:+.1f} {check.unit}",
            f"Δ {d_disp:+.1f} {check.unit} (baseline {b_disp:.1f}, mutated {m_disp:.1f})",
            ok,
        )

    if check.kind == "delta_positive_if_present":
        # Comme delta_positive, mais SKIP (status N/A) si baseline absent
        # (l'audio source ne contient pas la feature à booster).
        if b_raw is None or m_raw is None:
            return CheckResult(check.label, f"Δ ≥ {check.expected:+.2f}{check.unit}", "—", True, "skip (valeur absente)")
        b_disp = float(b_raw) * 100 if "%" in check.unit else float(b_raw)
        if b_disp < 0.5:
            return CheckResult(
                check.label,
                f"Δ ≥ {check.expected * 100:+.1f} {check.unit} (si baseline > 0.5%)",
                f"SKIP : baseline {b_disp:.1f}% trop faible (source sans contenu sub)",
                True,  # Pas un fail, on skip honnêtement
            )
        delta = float(m_raw) - float(b_raw)
        ok = delta >= float(check.expected)
        m_disp = float(m_raw) * 100 if "%" in check.unit else float(m_raw)
        d_disp = delta * 100 if "%" in check.unit else delta
        return CheckResult(
            check.label,
            f"Δ ≥ {check.expected * 100:+.1f} {check.unit}",
            f"Δ {d_disp:+.1f} {check.unit} (baseline {b_disp:.1f}, mutated {m_disp:.1f})",
            ok,
        )

    if check.kind == "categorical_same":
        # Vérifie que la valeur catégorielle (mode, etc.) est identique.
        if b_raw is None or m_raw is None:
            return CheckResult(check.label, "identique", "—", False, "valeur absente")
        ok = b_raw == m_raw
        return CheckResult(
            check.label,
            f"= {b_raw!r} (inchangé)",
            f"baseline={b_raw!r}, mutated={m_raw!r}",
            ok,
        )

    if check.kind == "ratio_max":
        # mutated / baseline < expected (= baisse importante)
        if b_raw is None or m_raw is None or b_raw == 0:
            return CheckResult(check.label, f"× ≤ {check.expected:.2f}", "—", False, "valeur absente")
        ratio = float(m_raw) / float(b_raw)
        ok = ratio <= float(check.expected)
        b_pct = float(b_raw) * 100
        m_pct = float(m_raw) * 100
        return CheckResult(
            check.label,
            f"× ≤ {check.expected:.2f} (baisse ≥{(1 - check.expected) * 100:.0f}%)",
            f"× {ratio:.2f} (baseline {b_pct:.1f}%, mutated {m_pct:.1f}%)",
            ok,
        )

    if check.kind == "note_shift":
        baseline_note = b_raw if isinstance(b_raw, str) else None
        mutated_note = m_raw if isinstance(m_raw, str) else None
        expected_note = _shift_note(baseline_note, int(check.expected))
        ok = mutated_note is not None and mutated_note == expected_note
        return CheckResult(
            check.label,
            f"{baseline_note or '?'} → {expected_note or '?'} (+{check.expected} demi-tons)",
            f"{baseline_note or '?'} → {mutated_note or '?'}",
            ok,
        )

    return CheckResult(check.label, "?", "?", False, f"kind inconnu: {check.kind}")


# ─── Pipeline d'exécution ─────────────────────────────────────────────────


def analyze_with_silence(audio_path: Path) -> dict:
    """Wrap analyze_track avec callbacks silencieux."""
    return analyze_track(audio_path)


def run_validation(source: Path, duration: float, sample_rate: int = 22050) -> int:
    """Charge le source, applique chaque transform, mesure les écarts.

    Retourne le nombre de checks en FAIL (0 = tous OK).
    """
    print(f"\nBeatfinder pipeline validation")
    print(f"Source        : {source}")
    print(f"Durée analysée: {duration:.0f}s (tronqué)")
    print(f"Sample rate   : {sample_rate} Hz")
    print("─" * 78)

    # Charge l'audio source (mono, sr=22050 comme le pipeline)
    print(f"\nChargement audio…", end=" ", flush=True)
    y_full, sr = librosa.load(source, sr=sample_rate, mono=True)
    n_samples = int(duration * sr)
    y = y_full[:n_samples] if len(y_full) > n_samples else y_full
    print(f"OK ({len(y) / sr:.1f}s, {len(y)} samples)")

    with tempfile.TemporaryDirectory(prefix="bf-validate-") as tmpdir:
        tmp = Path(tmpdir)

        # 1. Analyse baseline (audio tronqué non modifié)
        # WAV 32-bit float pour éviter le clipping sur les gains positifs
        # (un signal proche de 0 dBFS + gain +6 dB serait écrêté à 0 en PCM 16-bit
        # et l'écart attendu sur true_peak ne serait pas mesurable).
        baseline_path = tmp / "baseline.wav"
        sf.write(baseline_path, y, sr, subtype="FLOAT")
        print(f"Analyse baseline…", end=" ", flush=True)
        baseline = analyze_with_silence(baseline_path)
        print(
            f"OK  (LUFS={baseline['energy']['lufs_integrated']:.1f} dB, "
            f"BPM={baseline['tempo']['bpm']:.1f}, "
            f"key={baseline['tonality']['note']} {baseline['tonality']['mode']}, "
            f"centroid={baseline['spectral']['centroid_hz']:.0f} Hz)"
        )

        total_checks = 0
        total_ok = 0
        total_fail = 0

        for i, t in enumerate(TRANSFORMS, start=1):
            print(f"\n[{i}/{len(TRANSFORMS)}] {t.label}")
            try:
                y_mut = t.apply(y, sr)
            except Exception as exc:  # noqa: BLE001
                print(f"  ✕ transform a planté : {exc}")
                total_fail += len(t.checks)
                total_checks += len(t.checks)
                continue

            mut_path = tmp / f"mutated_{t.key}.wav"
            sf.write(mut_path, y_mut, sr, subtype="FLOAT")
            print(f"  → analyse mutated…", end=" ", flush=True)
            mutated = analyze_with_silence(mut_path)
            print("OK")

            # Tableau des checks
            print(f"\n  {'Feature':<22}{'Attendu':<38}{'Mesuré':<42}{'Statut'}")
            print(f"  {'-' * 22}{'-' * 38}{'-' * 42}{'-' * 8}")
            for c in t.checks:
                r = evaluate_check(c, baseline, mutated)
                total_checks += 1
                if r.ok:
                    total_ok += 1
                    status = "✓ OK"
                else:
                    total_fail += 1
                    status = "✕ FAIL"
                print(f"  {r.label:<22}{r.expected:<38}{r.measured:<42}{status}")
                if r.detail and not r.ok:
                    print(f"  {'':<22}{'':<38}{r.detail}")

        print("\n" + "─" * 78)
        if total_fail == 0:
            print(f"✓ {total_ok}/{total_checks} checks OK — pipeline cohérent")
        else:
            print(
                f"✕ {total_fail}/{total_checks} FAIL "
                f"({total_ok} OK) — vérifier les analyzers concernés"
            )

        return total_fail


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", type=Path, help="MP3 ou WAV à utiliser comme référence")
    parser.add_argument(
        "--duration", type=float, default=30.0,
        help="Durée en secondes à analyser (défaut 30s — gain perf vs morceau complet)",
    )
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"Fichier introuvable : {args.source}", file=sys.stderr)
        return 2

    return 1 if run_validation(args.source, args.duration) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
