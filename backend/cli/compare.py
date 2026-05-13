"""Compare deux playlists déjà analysées en DB et écrit un brief différentiel.

Usage :
    python -m backend.cli.compare <playlist_id_A> <playlist_id_B>
    python -m backend.cli.compare <id_A> <id_B> --output diff.md

Charge les patterns les plus récents pour chaque playlist (via PlaylistPattern.id
desc) et produit un markdown qui aligne médianes A vs B + delta pour toutes les
features clés. Utile pour mesurer le drift temporel ou la différence entre styles.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select

from backend.db import make_engine, make_session_factory
from backend.domain.models import Playlist, PlaylistPattern


@dataclass(slots=True)
class PlaylistSnapshot:
    spotify_id: str
    name: str
    n_tracks: int
    pattern: dict


def _load_snapshot(
    session, playlist_id: str, pattern_id: int | None = None,
) -> PlaylistSnapshot | None:
    """Charge un snapshot. Sans pattern_id, prend le pattern le plus récent.

    Avec pattern_id, prend ce pattern précis (utile pour comparer l'évolution
    d'une même playlist au fil de runs successifs).
    """
    playlist = session.scalar(
        select(Playlist).where(Playlist.spotify_id == playlist_id)
    )
    if not playlist:
        return None
    q = select(PlaylistPattern).where(PlaylistPattern.playlist_id == playlist.id)
    if pattern_id is not None:
        q = q.where(PlaylistPattern.id == pattern_id)
    else:
        q = q.order_by(PlaylistPattern.id.desc())
    pat = session.scalars(q).first()
    if not pat:
        return None
    suffix = f" (pattern #{pat.id})" if pattern_id is not None else ""
    return PlaylistSnapshot(
        spotify_id=playlist.spotify_id,
        name=playlist.name + suffix,
        n_tracks=pat.n_tracks_analyzed,
        pattern=pat.pattern_json,
    )


def _walk(d: dict | None, *path: str) -> Any:
    val: Any = d
    for p in path:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
        if val is None:
            return None
    return val


def _delta_str(a: float | None, b: float | None, fmt: str = "+.1f") -> str:
    if a is None or b is None:
        return "—"
    delta = b - a
    return format(delta, fmt)


def _num_row(
    label: str,
    a: PlaylistSnapshot,
    b: PlaylistSnapshot,
    *path: str,
    sub_key: str = "median",
    fmt: str = ".1f",
    delta_fmt: str | None = None,
) -> str:
    va = _walk(a.pattern, *path, sub_key)
    vb = _walk(b.pattern, *path, sub_key)
    # Delta format = fmt préfixé par + pour signer, en évitant le double + si fmt l'a déjà
    if delta_fmt is None:
        delta_fmt = fmt if fmt.startswith("+") else f"+{fmt}"
    va_s = format(va, fmt) if isinstance(va, (int, float)) else "—"
    vb_s = format(vb, fmt) if isinstance(vb, (int, float)) else "—"
    delta = _delta_str(va, vb, delta_fmt)
    return f"| {label} | {va_s} | {vb_s} | {delta} |"


def _dist_summary(dist: dict, key: str, fmt: str = ".0%") -> str:
    """Renvoie une string de type 'minor 82% / major 18%' depuis distribution."""
    if not dist:
        return "—"
    items = sorted(dist.items(), key=lambda x: -x[1])
    return " / ".join(f"{k} {format(v, fmt)}" for k, v in items[:3])


def build_diff_markdown(a: PlaylistSnapshot, b: PlaylistSnapshot) -> str:
    """Produit le brief diff complet en markdown."""
    md: list[str] = []
    md.append(f"# Diff : {a.name} → {b.name}")
    md.append("")
    md.append(
        f"_A = **{a.name}** ({a.n_tracks} tracks) — B = **{b.name}** ({b.n_tracks} tracks). "
        "Δ = B − A._"
    )
    md.append("")

    # TL;DR : les écarts les plus significatifs
    md.append("## TL;DR")
    md.append("")
    bpm_a = _walk(a.pattern, "tempo", "bpm", "median")
    bpm_b = _walk(b.pattern, "tempo", "bpm", "median")
    lufs_a = _walk(a.pattern, "energy", "lufs_integrated", "median")
    lufs_b = _walk(b.pattern, "energy", "lufs_integrated", "median")
    sub_a = _walk(a.pattern, "spectral", "band_energy", "sub", "median")
    sub_b = _walk(b.pattern, "spectral", "band_energy", "sub", "median")
    bass_a = _walk(a.pattern, "spectral", "band_energy", "bass", "median")
    bass_b = _walk(b.pattern, "spectral", "band_energy", "bass", "median")
    lowend_a = (sub_a or 0) + (bass_a or 0)
    lowend_b = (sub_b or 0) + (bass_b or 0)

    if bpm_a and bpm_b:
        md.append(
            f"- **BPM** : {bpm_a:.0f} → {bpm_b:.0f} "
            f"({_delta_str(bpm_a, bpm_b, '+.0f')} BPM)"
        )
    if lufs_a and lufs_b:
        md.append(
            f"- **LUFS** : {lufs_a:+.1f} → {lufs_b:+.1f} "
            f"({_delta_str(lufs_a, lufs_b, '+.1f')} dB)"
        )
    if lowend_a and lowend_b:
        md.append(
            f"- **Low-end (sub+bass)** : {lowend_a * 100:.0f}% → "
            f"{lowend_b * 100:.0f}% "
            f"({_delta_str(lowend_a * 100, lowend_b * 100, '+.0f')} pts)"
        )

    mode_a = _walk(a.pattern, "tonality", "mode", "distribution") or {}
    mode_b = _walk(b.pattern, "tonality", "mode", "distribution") or {}
    minor_a = mode_a.get("minor", 0) * 100
    minor_b = mode_b.get("minor", 0) * 100
    md.append(
        f"- **Mineur** : {minor_a:.0f}% → {minor_b:.0f}% "
        f"({_delta_str(minor_a, minor_b, '+.0f')} pts)"
    )
    md.append("")

    # Tempo
    md.append("## Tempo")
    md.append("")
    md.append("| | A | B | Δ |")
    md.append("|---|---|---|---|")
    md.append(_num_row("BPM médian", a, b, "tempo", "bpm", fmt=".1f"))
    md.append(_num_row("BPM p25", a, b, "tempo", "bpm", sub_key="p25", fmt=".0f"))
    md.append(_num_row("BPM p75", a, b, "tempo", "bpm", sub_key="p75", fmt=".0f"))
    md.append(_num_row("BPM std", a, b, "tempo", "bpm", sub_key="std", fmt=".1f"))
    md.append(_num_row("Onset density", a, b, "tempo", "onset_density", fmt=".2f"))
    md.append(_num_row("Beat consistency", a, b, "tempo", "beat_consistency", fmt=".2f"))
    md.append("")

    # Tonalité
    md.append("## Tonalité")
    md.append("")
    md.append("| | A | B |")
    md.append("|---|---|---|")
    md.append(
        f"| Mode | {_dist_summary(mode_a, 'mode')} | {_dist_summary(mode_b, 'mode')} |"
    )
    note_a = _walk(a.pattern, "tonality", "note", "distribution") or {}
    note_b = _walk(b.pattern, "tonality", "note", "distribution") or {}
    md.append(
        f"| Top 3 racines | {_dist_summary(note_a, 'note')} | {_dist_summary(note_b, 'note')} |"
    )
    aa = _walk(a.pattern, "tonality", "all_agree_ratio")
    ab = _walk(b.pattern, "tonality", "all_agree_ratio")
    aa_s = f"{aa * 100:.0f}%" if aa is not None else "—"
    ab_s = f"{ab * 100:.0f}%" if ab is not None else "—"
    md.append(f"| Tracks vote 3/3 | {aa_s} | {ab_s} |")
    md.append("")

    # Énergie
    md.append("## Énergie & mastering")
    md.append("")
    md.append("| | A | B | Δ |")
    md.append("|---|---|---|---|")
    md.append(_num_row("LUFS médian", a, b, "energy", "lufs_integrated", fmt="+.1f"))
    md.append(_num_row("True peak médian", a, b, "energy", "true_peak_db", fmt="+.1f"))
    md.append(_num_row("Crest factor", a, b, "energy", "crest_factor_db", fmt=".1f"))
    md.append(_num_row("DR (p95-p10)", a, b, "energy", "dynamic_range_db", fmt=".1f"))
    md.append("")

    # Spectral bands
    md.append("## Profil spectral")
    md.append("")
    md.append("| Bande | A | B | Δ (pts) |")
    md.append("|-------|---|---|---------|")
    for band, label in [
        ("sub", "Sub"),
        ("bass", "Bass"),
        ("low_mid", "Low-mid"),
        ("mid", "Mid"),
        ("high_mid", "High-mid"),
        ("high", "High"),
    ]:
        va = _walk(a.pattern, "spectral", "band_energy", band, "median")
        vb = _walk(b.pattern, "spectral", "band_energy", band, "median")
        va_s = f"{va * 100:.1f}%" if va is not None else "—"
        vb_s = f"{vb * 100:.1f}%" if vb is not None else "—"
        delta = (
            f"{(vb - va) * 100:+.1f}"
            if (va is not None and vb is not None)
            else "—"
        )
        md.append(f"| {label} | {va_s} | {vb_s} | {delta} |")
    md.append("")
    md.append("| | A | B | Δ |")
    md.append("|---|---|---|---|")
    md.append(_num_row("Centroid (Hz)", a, b, "spectral", "centroid_hz", fmt=".0f"))
    md.append(_num_row("Rolloff 85% (Hz)", a, b, "spectral", "rolloff85_hz", fmt=".0f"))
    md.append("")

    # Structure
    md.append("## Structure")
    md.append("")
    md.append("| | A | B | Δ |")
    md.append("|---|---|---|---|")
    md.append(_num_row("Drop position (médiane)", a, b, "structure", "drop_position_ratio", fmt=".2f"))
    md.append(_num_row("Drop position (p25)", a, b, "structure", "drop_position_ratio", sub_key="p25", fmt=".2f"))
    md.append(_num_row("Drop position (p75)", a, b, "structure", "drop_position_ratio", sub_key="p75", fmt=".2f"))
    md.append(_num_row("Sections (médiane)", a, b, "structure", "n_sections", fmt=".0f"))
    md.append(_num_row("Durée (sec)", a, b, "duration_sec", fmt=".0f"))
    md.append("")

    return "\n".join(md)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Diff entre deux playlists déjà analysées en DB.",
    )
    parser.add_argument("playlist_a", help="Spotify playlist ID A (référence)")
    parser.add_argument("playlist_b", help="Spotify playlist ID B (à comparer)")
    parser.add_argument(
        "--pattern-a", type=int, default=None,
        help="ID pattern précis pour A (sinon le plus récent).",
    )
    parser.add_argument(
        "--pattern-b", type=int, default=None,
        help="ID pattern précis pour B (sinon le plus récent).",
    )
    parser.add_argument(
        "--output", "-o",
        help="Écrire le markdown dans ce fichier au lieu de stdout.",
    )
    args = parser.parse_args()

    Session = make_session_factory(make_engine())
    with Session() as s:
        a = _load_snapshot(s, args.playlist_a, pattern_id=args.pattern_a)
        b = _load_snapshot(s, args.playlist_b, pattern_id=args.pattern_b)
        if a is None:
            print(f"Playlist A {args.playlist_a!r} pas en DB.", file=sys.stderr)
            return 1
        if b is None:
            print(f"Playlist B {args.playlist_b!r} pas en DB.", file=sys.stderr)
            return 1
        md = build_diff_markdown(a, b)

    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"Diff écrit : {args.output}", file=sys.stderr)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
