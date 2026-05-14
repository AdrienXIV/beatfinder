"""Helpers pour appliquer un TrackOverride sur un dict de features audio.

L'override permet à l'utilisateur de corriger BPM / note / mode quand
l'analyse algorithmique est trompée (ambiguïté triolet pour le tempo,
consensus 3-voters faux pour la tonalité).

Le helper `apply_overrides` retourne un nouveau dict avec les valeurs
substituées — il ne modifie pas le dict original (immutable côté analyse).

`regenerate_playlist_patterns_for_track` recalcule le pattern agrégé de
toutes les playlists contenant la track impactée, en appliquant tous les
overrides existants. Appelé après chaque PATCH/DELETE d'override.
"""
from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.models import (
    CreativeSession,
    Playlist,
    PlaylistPattern,
    PlaylistTrack,
    Track,
    TrackAnalysis,
    TrackOverride,
)

log = logging.getLogger(__name__)

VALID_NOTES = frozenset(
    ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"),
)
VALID_MODES = frozenset(("major", "minor"))


def apply_overrides(features: dict, override: TrackOverride | None) -> dict:
    """Retourne un dict features avec les valeurs override substituées.

    Si override est None, retourne `features` tel quel (par référence — pas
    de copie pour économiser la mémoire). Si override est présent, retourne
    une copie profonde avec les substitutions.
    """
    if override is None:
        return features
    has_any = (
        override.bpm is not None
        or override.key_note is not None
        or override.key_mode is not None
    )
    if not has_any:
        return features

    out = deepcopy(features)
    if override.bpm is not None:
        tempo = out.setdefault("tempo", {})
        tempo["bpm"] = float(override.bpm)
    if override.key_note is not None or override.key_mode is not None:
        tonality = out.setdefault("tonality", {})
        if override.key_note is not None:
            tonality["note"] = override.key_note
        if override.key_mode is not None:
            tonality["mode"] = override.key_mode
        # Synchroniser le champ `key` composé (utilisé par certains modules).
        note = tonality.get("note", "?")
        mode = tonality.get("mode", "?")
        tonality["key"] = f"{note} {mode}".strip()
    return out


def regenerate_pattern_for_playlist(
    session: Session, playlist: Playlist, data_dir: Path | None = None,
) -> dict | None:
    """Recalcule et persiste un nouveau pattern pour cette playlist.

    Lit toutes les `TrackAnalysis` les plus récentes des tracks de la playlist,
    applique les `TrackOverride` éventuels, puis appelle `extract_pattern`
    sur les features mises à jour.

    Persiste un **nouveau** `PlaylistPattern` (conserve l'historique des
    anciennes analyses). Invalide le brief markdown en cache si data_dir
    fourni.

    Retourne le pattern_json calculé, ou None si la playlist n'a aucune
    track analysée.
    """
    from backend.local_projects import brief_filename
    from backend.services.pattern_extractor import extract_pattern

    track_features: list[dict] = []
    for pt in playlist.tracks:
        analysis = session.scalar(
            select(TrackAnalysis)
            .where(TrackAnalysis.track_id == pt.track_id)
            .order_by(TrackAnalysis.id.desc()),
        )
        if analysis is None:
            continue
        override = session.scalar(
            select(TrackOverride).where(TrackOverride.track_id == pt.track_id),
        )
        track_features.append(apply_overrides(analysis.features_json, override))

    if not track_features:
        return None

    pattern = extract_pattern(track_features)
    session.add(
        PlaylistPattern(
            playlist_id=playlist.id,
            pattern_json=pattern,
            n_tracks_analyzed=len(track_features),
        ),
    )

    if data_dir is not None:
        brief_path = data_dir / "reports" / f"{brief_filename(playlist.spotify_id)}.md"
        if brief_path.is_file():
            try:
                brief_path.unlink()
            except OSError as exc:
                log.warning(
                    "Could not invalidate brief cache %s: %s", brief_path, exc,
                )

    return pattern


def regenerate_playlist_patterns_for_track(
    session: Session, track_id: int, data_dir: Path | None = None,
) -> list[str]:
    """Régénère le PlaylistPattern de toutes les playlists contenant cette track.

    Wrapper sur `regenerate_pattern_for_playlist` qui itère sur les playlists
    impactées par une track donnée (cas typique : après un PATCH/DELETE override).
    """
    impacted = session.scalars(
        select(Playlist)
        .join(PlaylistTrack, PlaylistTrack.playlist_id == Playlist.id)
        .where(PlaylistTrack.track_id == track_id)
        .distinct(),
    ).all()

    impacted_ids: list[str] = []
    for p in impacted:
        if regenerate_pattern_for_playlist(session, p, data_dir) is not None:
            impacted_ids.append(p.spotify_id)

    session.commit()
    log.info(
        "Regenerated pattern for %d playlist(s) after track %d override change",
        len(impacted_ids), track_id,
    )
    return impacted_ids


def propagate_override_to_active_sessions(
    session: Session, track: Track, data_dir: Path | None = None,
) -> list[str]:
    """Propage un override de track aux sessions actives qui la ciblent.

    Quand l'utilisateur corrige manuellement le BPM/key d'une track, on
    régénère le `target_pattern_json` + `plan_md` des `CreativeSession` actives
    (non archivées) dont `target_kind='spotify_track'` et `target_ref=track.spotify_id`.

    La verrouillage de la cible reste valide vs les re-analyses automatiques :
    on ne touche aux sessions que sur action utilisateur explicite (override).

    Retourne la liste des `session.spotify_id` impactés.
    """
    from backend.services.pattern_extractor import extract_pattern
    from backend.services.session_brief import generate_session_brief

    sessions_to_update = session.scalars(
        select(CreativeSession).where(
            CreativeSession.target_kind == "spotify_track",
            CreativeSession.target_ref == track.spotify_id,
            CreativeSession.archived == False,  # noqa: E712
        ),
    ).all()

    if not sessions_to_update:
        return []

    analysis = session.scalar(
        select(TrackAnalysis)
        .where(TrackAnalysis.track_id == track.id)
        .order_by(TrackAnalysis.id.desc()),
    )
    if analysis is None:
        return []

    override = session.scalar(
        select(TrackOverride).where(TrackOverride.track_id == track.id),
    )
    features = apply_overrides(analysis.features_json, override)
    new_pattern = extract_pattern([features])

    impacted_ids: list[str] = []
    for sess in sessions_to_update:
        sess.target_pattern_json = new_pattern
        sess.plan_md = generate_session_brief(
            new_pattern,
            target_name=sess.target_name,
            ambiance=sess.ambiance_json,
        )
        impacted_ids.append(sess.spotify_id)

    log.info(
        "Propagated track %s override to %d active session(s)",
        track.spotify_id, len(impacted_ids),
    )
    return impacted_ids


def compute_confidence(features: dict) -> tuple[bool, list[str]]:
    """Détermine si l'analyse de cette track est suspecte + liste les raisons.

    Critères :
    - `bpm_confidence < 1.0` : les 2 détecteurs BPM ne convergent pas.
    - `vote_count < 3` : les 3 algos de tonalité ne sont pas unanimes.
    - **half-time/triplet** : si `60 ≤ BPM ≤ 130` ET `onset_density > 4`,
      le beat tracker s'est probablement accroché à une grille en triplets
      ou en half-time (cas typique des grooves Drake / autotune-heavy).
    - **CNN incertain** : `madmom_confidence < 0.85` indique que le modèle
      CNN n'est pas sûr de sa réponse même si les autres algos sont d'accord.

    Returns: (confidence_low: bool, reasons: list[str]).
    """
    tempo = features.get("tempo") or {}
    tonality = features.get("tonality") or {}
    reasons: list[str] = []

    bpm = tempo.get("bpm")
    bpm_conf = tempo.get("bpm_confidence")
    onset = tempo.get("onset_density")
    vote = tonality.get("vote_count")
    madmom_conf = tonality.get("madmom_confidence")

    if isinstance(bpm_conf, (int, float)) and bpm_conf < 1:
        reasons.append("Les 2 détecteurs BPM divergent")
    if (
        isinstance(bpm, (int, float))
        and isinstance(onset, (int, float))
        and 60 <= bpm <= 130
        and onset > 4
    ):
        reasons.append(
            "BPM probable half-time/triplet "
            f"(grille à {bpm:.0f} avec onset {onset:.1f}/s suspect — vérifier "
            f"x1.5 = {bpm * 1.5:.0f} ou x2 = {bpm * 2:.0f})"
        )
    if isinstance(vote, (int, float)) and vote < 3:
        reasons.append(f"Algos tonalité en désaccord (vote {int(vote)}/3)")
    if isinstance(madmom_conf, (int, float)) and madmom_conf < 0.85:
        reasons.append(
            f"CNN tonalité peu sûr ({madmom_conf:.0%} de confiance)"
        )

    return len(reasons) > 0, reasons


def bpm_alt_hypotheses(bpm: float | None) -> list[float]:
    """Retourne 4 alternatives musicalement plausibles : ×2, /2, ×1.5, /1.5.

    Ne garde que celles qui tombent dans la zone [50, 200] BPM (musical).
    Trié croissant. Sans doublon.
    """
    if bpm is None or bpm <= 0:
        return []
    candidates = {
        round(bpm * 2.0, 1),
        round(bpm / 2.0, 1),
        round(bpm * 1.5, 1),
        round(bpm / 1.5, 1),
    }
    candidates.discard(round(bpm, 1))
    return sorted(c for c in candidates if 50.0 <= c <= 200.0)
