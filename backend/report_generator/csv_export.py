"""Export CSV des features per-track (compatible Obsidian/Notion)."""
from __future__ import annotations

import csv
import io
from typing import Any


def generate_csv(tracks_data: list[dict]) -> str:
    """Export per-track des features clés au format CSV (compatible Obsidian/Notion).

    Colonnes choisies pour permettre filtre/tri sur tableur : tonalité avec vote,
    énergie complète, profil spectral détaillé, position drop et durée. Pas de
    métadonnées playlist (juste les rows tracks).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "artist", "title", "bpm", "key", "mode", "root", "vote_count",
        "all_agree", "lufs", "true_peak", "dynamic_range_db", "crest_factor_db",
        "sub_pct", "bass_pct", "low_mid_pct", "mid_pct", "high_mid_pct", "high_pct",
        "centroid_hz", "drop_pct", "n_sections", "n_modulations", "duration_sec",
    ])
    for t in tracks_data:
        f = t.get("features") or {}
        tempo_f = f.get("tempo") or {}
        ton_f = f.get("tonality") or {}
        energy_f = f.get("energy") or {}
        spectral_f = f.get("spectral") or {}
        band_f = spectral_f.get("band_energy") or {}
        struct_f = f.get("structure") or {}

        def pct(b: str) -> str:
            v = band_f.get(b)
            return f"{v * 100:.1f}" if v is not None else ""

        def num(v: Any, fmt: str = ".2f") -> str:
            return format(v, fmt) if isinstance(v, (int, float)) else ""

        writer.writerow([
            t.get("artist") or "",
            t.get("title") or "",
            num(tempo_f.get("bpm"), ".1f"),
            ton_f.get("key") or "",
            ton_f.get("mode") or "",
            ton_f.get("note") or "",
            ton_f.get("vote_count") or "",
            "1" if ton_f.get("methods_agree_all") else "0",
            num(energy_f.get("lufs_integrated")),
            num(energy_f.get("true_peak_db")),
            num(energy_f.get("dynamic_range_db")),
            num(energy_f.get("crest_factor_db")),
            pct("sub"),
            pct("bass"),
            pct("low_mid"),
            pct("mid"),
            pct("high_mid"),
            pct("high"),
            num(spectral_f.get("centroid_hz"), ".0f"),
            num(
                (struct_f.get("drop_position_ratio") or 0) * 100,
                ".1f",
            ) if struct_f.get("drop_position_ratio") is not None else "",
            num(struct_f.get("n_sections"), ".0f"),
            num(ton_f.get("n_modulations"), ".0f"),
            num(f.get("duration_sec"), ".0f"),
        ])
    return buf.getvalue()
