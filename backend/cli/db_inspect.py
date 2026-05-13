"""Inspecteur DB : tableau per-track + pattern global d'une playlist analysée.

Renommé depuis backend.inspect / backend.db_inspect pour ne plus shadow le module
stdlib `inspect` et regrouper toutes les commandes CLI dans `backend.cli/`.

Lit la dernière analyse de chaque track + le dernier pattern de la playlist.

Usage :
    python -m backend.cli.db_inspect <spotify_playlist_id>
    python -m backend.cli.db_inspect 0AxKYXcQKwLN04Ok73L8y6
"""
from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv
from sqlalchemy import select

from backend.db import make_engine, make_session_factory
from backend.domain.models import Playlist, PlaylistPattern, TrackAnalysis

COLS = (
    ("#", 3),
    ("Artist", 20),
    ("Title", 26),
    ("BPM", 6),
    ("Key", 11),
    ("V", 3),
    ("cens", 9),
    ("cqt", 9),
    ("mm", 9),
    ("LUFS", 7),
    ("TP", 6),
    ("DR", 5),
    ("S+B", 5),
    ("Drop", 5),
)


def _fmt_row(values: list[str]) -> str:
    return " | ".join(
        f"{v:<{w}}" for v, (_, w) in zip(values, COLS, strict=False)
    )


def _table(session, playlist: Playlist) -> None:
    pt_rows = sorted(playlist.tracks, key=lambda x: x.position)
    print(_fmt_row([h for h, _ in COLS]))
    print("-" * (sum(w for _, w in COLS) + 3 * (len(COLS) - 1)))

    for pt in pt_rows:
        t = pt.track
        a = session.scalars(
            select(TrackAnalysis)
            .where(TrackAnalysis.track_id == t.id)
            .order_by(TrackAnalysis.id.desc())
        ).first()
        if not a:
            print(_fmt_row([str(pt.position + 1), t.artist[:22], t.title[:28], "(no data)"]))
            continue

        f = a.features_json
        tempo = f.get("tempo") or {}
        ton = f.get("tonality") or {}
        energy = f.get("energy") or {}
        band = (f.get("spectral") or {}).get("band_energy") or {}
        struct = f.get("structure") or {}

        uncertain = "*" if ton.get("is_uncertain") else " "
        sub_bass = ((band.get("sub") or 0) + (band.get("bass") or 0)) * 100
        lufs = energy.get("lufs_integrated")
        tp = energy.get("true_peak_db")
        dr = energy.get("dynamic_range_db")

        def _short_key(k: str | None) -> str:
            if not k:
                return "?"
            parts = k.split()
            note = parts[0]
            mode = parts[1].lower()[:3] if len(parts) > 1 else "?"
            return f"{note} {mode}"

        print(_fmt_row([
            str(pt.position + 1),
            t.artist[:20],
            t.title[:26],
            f"{tempo.get('bpm', 0):.1f}",
            f"{ton.get('key', '?')[:9]}{uncertain}",
            f"{ton.get('vote_count', 0)}/3",
            _short_key(ton.get("ks_cens_key")),
            _short_key(ton.get("ks_cqt_key")),
            _short_key(ton.get("madmom_key")),
            f"{lufs:+.1f}" if lufs is not None else "—",
            f"{tp:+.1f}" if tp is not None else "—",
            f"{dr:.1f}" if dr is not None else "—",
            f"{sub_bass:.0f}%",
            f"{(struct.get('drop_position_ratio') or 0) * 100:.0f}%",
        ]))


def _global_pattern(session, playlist: Playlist) -> None:
    pat_obj = session.scalars(
        select(PlaylistPattern)
        .where(PlaylistPattern.playlist_id == playlist.id)
        .order_by(PlaylistPattern.id.desc())
    ).first()
    if not pat_obj:
        print("(pas de pattern enregistré)")
        return

    p = pat_obj.pattern_json
    bpm = p["tempo"]["bpm"]
    ton = p["tonality"]
    e = p["energy"]
    sp = p["spectral"]
    st = p["structure"]

    print(f"BPM           : médian {bpm['median']:.1f} ± {bpm['std']:.1f}  "
          f"(range {bpm['min']:.0f}–{bpm['max']:.0f})")
    print(f"Onset density : médian {p['tempo']['onset_density']['median']:.2f} /sec")
    print()
    print(f"Key common    : {ton['key']['most_common']}")
    print(f"Mode dist     : {ton['mode']['distribution']}")
    print(f"Root common   : {ton['most_common_root']['most_common']}")
    print(f"Uncertain     : {ton['uncertain_ratio'] * 100:.0f}% des tracks")
    print(f"Modulations   : médian {ton['n_modulations']['median']:.0f}/track")
    print()
    print(f"LUFS          : médian {e['lufs_integrated']['median']:.2f} dB  "
          f"(p25={e['lufs_integrated']['p25']:.1f} / p75={e['lufs_integrated']['p75']:.1f})")
    print(f"True peak     : médian {e['true_peak_db']['median']:.2f} dBFS  "
          f"(max {e['true_peak_db']['max']:.2f})")
    print(f"Crest factor  : médian {e['crest_factor_db']['median']:.2f} dB")
    print(f"DR p95-p10    : médian {e['dynamic_range_db']['median']:.2f} dB")
    print()
    print(f"Centroid      : médian {sp['centroid_hz']['median']:.0f} Hz")
    print(f"Rolloff85     : médian {sp['rolloff85_hz']['median']:.0f} Hz")
    print(f"Flatness      : médian {sp['flatness']['median']:.4f}")
    print()
    print("Bandes critiques (médianes, 0..1) :")
    for band_name, stats in sp["band_energy"].items():
        bar = "█" * int(stats["median"] * 60)
        print(f"  {band_name:9} {stats['median']:.3f}  {bar}")
    print()
    print(f"Sections      : médian {st['n_sections']['median']:.0f}")
    print(f"Drop pos      : médian {st['drop_position_ratio']['median'] * 100:.0f}% du track")


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("playlist_id", help="Spotify playlist ID (22 chars)")
    args = parser.parse_args()

    Session = make_session_factory(make_engine())
    with Session() as s:
        playlist = s.scalar(
            select(Playlist).where(Playlist.spotify_id == args.playlist_id)
        )
        if not playlist:
            print(
                f"Playlist {args.playlist_id!r} pas en base. "
                "Lance d'abord --analyze --save sur cette playlist.",
                file=sys.stderr,
            )
            return 1

        n_tracks = len(playlist.tracks)
        print(f"=== {playlist.name} ({n_tracks} tracks) ===\n")
        _table(s, playlist)
        print()
        print("=== Pattern global ===")
        print()
        _global_pattern(s, playlist)
        print()
        print("(* = tonalité incertaine)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
