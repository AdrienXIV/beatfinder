"""Routes FastAPI playlists (sprint 3b).

  GET  /playlists                                       : liste + stats agrégées
  GET  /playlists/{spotify_id}                          : détail + tracks + patterns
  GET  /playlists/{spotify_id}/patterns                 : historique patterns
  GET  /playlists/{spotify_id}/patterns/{pattern_id}    : pattern JSON brut
  POST /playlists/analyze                               : déclenche pipeline (job)
"""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.api.deps import get_job_queue, get_session
from backend.api.job_runner import run_analyze_job
from backend.api.jobs import JobQueue
from backend.api.schemas import (
    AnalyzeRequest,
    JobOut,
    PatternOut,
    PatternSummaryOut,
    PlaylistDetailOut,
    PlaylistSummaryOut,
    TrackOut,
)
from backend.domain.models import (
    Playlist,
    PlaylistPattern,
    PlaylistTrack,
    TrackAnalysis,
)
from backend.infrastructure.settings_store import load_settings

router = APIRouter(prefix="/playlists", tags=["playlists"])

SessionDep = Annotated[Session, Depends(get_session)]
QueueDep = Annotated[JobQueue, Depends(get_job_queue)]


def _load_playlist_or_404(session: Session, spotify_id: str) -> Playlist:
    p = session.scalar(
        select(Playlist).where(Playlist.spotify_id == spotify_id),
    )
    if p is None:
        raise HTTPException(
            status_code=404, detail=f"Playlist {spotify_id!r} not found",
        )
    return p


@router.get("", response_model=list[PlaylistSummaryOut])
def list_playlists(session: SessionDep) -> list[PlaylistSummaryOut]:
    """Liste playlists avec stats agrégées (n_tracks, n_patterns, last_pattern)."""
    tracks_count_subq = (
        select(
            PlaylistTrack.playlist_id,
            func.count(PlaylistTrack.track_id).label("n"),
        )
        .group_by(PlaylistTrack.playlist_id)
        .subquery()
    )
    patterns_agg_subq = (
        select(
            PlaylistPattern.playlist_id,
            func.count(PlaylistPattern.id).label("n"),
            func.max(PlaylistPattern.created_at).label("last"),
        )
        .group_by(PlaylistPattern.playlist_id)
        .subquery()
    )

    stmt = (
        select(
            Playlist,
            func.coalesce(tracks_count_subq.c.n, 0).label("n_tracks"),
            func.coalesce(patterns_agg_subq.c.n, 0).label("n_patterns"),
            patterns_agg_subq.c.last.label("last_analyzed_at"),
        )
        .select_from(Playlist)
        .outerjoin(
            tracks_count_subq,
            tracks_count_subq.c.playlist_id == Playlist.id,
        )
        .outerjoin(
            patterns_agg_subq,
            patterns_agg_subq.c.playlist_id == Playlist.id,
        )
        .order_by(Playlist.updated_at.desc())
    )

    rows = session.execute(stmt).all()
    return [
        PlaylistSummaryOut(
            spotify_id=p.spotify_id,
            name=p.name,
            owner_display_name=p.owner_display_name,
            description=p.description,
            n_tracks=int(n_tracks),
            n_patterns=int(n_patterns),
            last_analyzed_at=last_analyzed_at,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p, n_tracks, n_patterns, last_analyzed_at in rows
    ]


@router.get("/{spotify_id}", response_model=PlaylistDetailOut)
def get_playlist(spotify_id: str, session: SessionDep) -> PlaylistDetailOut:
    """Détail playlist : meta + tracks (avec presence analysis) + patterns."""
    p = session.scalar(
        select(Playlist)
        .where(Playlist.spotify_id == spotify_id)
        .options(
            selectinload(Playlist.tracks).selectinload(PlaylistTrack.track),
            selectinload(Playlist.patterns),
        ),
    )
    if p is None:
        raise HTTPException(
            status_code=404, detail=f"Playlist {spotify_id!r} not found",
        )

    pt_rows = sorted(p.tracks, key=lambda x: x.position)
    track_ids = [pt.track_id for pt in pt_rows]

    latest_by_track: dict[int, TrackAnalysis] = {}
    if track_ids:
        last_ids_subq = (
            select(func.max(TrackAnalysis.id))
            .where(TrackAnalysis.track_id.in_(track_ids))
            .group_by(TrackAnalysis.track_id)
            .scalar_subquery()
        )
        latest_rows = session.scalars(
            select(TrackAnalysis).where(TrackAnalysis.id.in_(last_ids_subq)),
        ).all()
        for a in latest_rows:
            latest_by_track[a.track_id] = a

    tracks_out = [
        TrackOut(
            spotify_id=pt.track.spotify_id,
            title=pt.track.title,
            artist=pt.track.artist,
            duration_ms=pt.track.duration_ms,
            release_date=pt.track.release_date,
            position=pt.position,
            has_analysis=pt.track_id in latest_by_track,
            audio_path=(
                latest_by_track[pt.track_id].audio_path
                if pt.track_id in latest_by_track
                else None
            ),
        )
        for pt in pt_rows
    ]

    patterns = sorted(p.patterns, key=lambda pat: pat.id, reverse=True)
    patterns_out = [_pattern_to_summary(pat) for pat in patterns]
    latest_pattern_json = patterns[0].pattern_json if patterns else None

    return PlaylistDetailOut(
        spotify_id=p.spotify_id,
        name=p.name,
        owner_display_name=p.owner_display_name,
        description=p.description,
        tracks=tracks_out,
        patterns=patterns_out,
        latest_pattern=latest_pattern_json,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _pattern_to_summary(pat: PlaylistPattern) -> PatternSummaryOut:
    """Extrait les médianes principales du pattern_json pour le résumé."""
    pj = pat.pattern_json or {}

    def _walk(*path: str) -> float | None:
        v = pj
        for p in path:
            if not isinstance(v, dict):
                return None
            v = v.get(p)
            if v is None:
                return None
        return float(v) if isinstance(v, (int, float)) else None

    minor = None
    mode_dist = (pj.get("tonality", {}) or {}).get("mode", {}).get("distribution") or {}
    if "minor" in mode_dist:
        try:
            minor = float(mode_dist["minor"])
        except (TypeError, ValueError):
            minor = None

    return PatternSummaryOut(
        id=pat.id,
        n_tracks_analyzed=pat.n_tracks_analyzed,
        analyzer_version=pat.analyzer_version,
        created_at=pat.created_at,
        bpm_median=_walk("tempo", "bpm", "median"),
        lufs_median=_walk("energy", "lufs_integrated", "median"),
        sub_median=_walk("spectral", "band_energy", "sub", "median"),
        bass_median=_walk("spectral", "band_energy", "bass", "median"),
        minor_ratio=minor,
    )


@router.get("/{spotify_id}/patterns", response_model=list[PatternSummaryOut])
def list_patterns(
    spotify_id: str, session: SessionDep,
) -> list[PatternSummaryOut]:
    p = _load_playlist_or_404(session, spotify_id)
    patterns = sorted(p.patterns, key=lambda pat: pat.id, reverse=True)
    return [_pattern_to_summary(pat) for pat in patterns]


@router.post(
    "/analyze", response_model=JobOut, status_code=202,
)
async def trigger_analyze(
    payload: AnalyzeRequest, queue: QueueDep,
) -> JobOut:
    """Crée un job + spawn background task. Suivre via /api/jobs/{id}/stream.

    Refuse 400 si Spotify n'est pas configuré (évite de lancer un job qui va
    crash 20s plus tard avec un message obscur).
    """
    settings = load_settings()
    if not settings.spotify.is_configured:
        raise HTTPException(
            status_code=400,
            detail=(
                "Spotify n'est pas configuré. Va dans Paramètres et saisis "
                "ton CLIENT_ID + CLIENT_SECRET (developer.spotify.com)."
            ),
        )

    job = queue.create("analyze")
    task = asyncio.create_task(
        run_analyze_job(queue, job.id, payload), name=f"analyze:{job.id}",
    )
    queue.attach_task(job.id, task)
    return JobOut(**job.to_dict())


@router.get(
    "/{spotify_id}/patterns/{pattern_id}", response_model=PatternOut,
)
def get_pattern(
    spotify_id: str, pattern_id: int, session: SessionDep,
) -> PatternOut:
    p = _load_playlist_or_404(session, spotify_id)
    pat = session.scalar(
        select(PlaylistPattern).where(
            PlaylistPattern.id == pattern_id,
            PlaylistPattern.playlist_id == p.id,
        ),
    )
    if pat is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Pattern {pattern_id} not found for playlist {spotify_id!r}"
            ),
        )
    return PatternOut(
        id=pat.id,
        playlist_spotify_id=p.spotify_id,
        n_tracks_analyzed=pat.n_tracks_analyzed,
        analyzer_version=pat.analyzer_version,
        pattern=pat.pattern_json,
        created_at=pat.created_at,
    )
