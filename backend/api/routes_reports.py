"""Routes FastAPI reports (sprint 3b).

  GET  /playlists/{spotify_id}/brief         : markdown rendu, cache .md auto
  GET  /playlists/{spotify_id}/brief.md      : export markdown brut (téléchargement)
  GET  /playlists/{spotify_id}/brief.pdf     : PDF via Chromium headless (fidélité 100%)
  POST /compare                              : diff markdown entre 2 playlists
  GET  /compare/multi?ids=A,B,C              : radar + stats pour 2 à 5 sources
  GET  /tracks/{spotify_id}/analysis         : features brut + meta d'une track
  POST /tracks/analyze                       : crée un job pour analyser une track isolée
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import get_data_dir, get_job_queue, get_session
from backend.api.job_runner import run_track_analyze_job
from backend.api.jobs import JobQueue
from backend.api.schemas import (
    AnalyzeTrackRequest,
    BriefOut,
    CompareOut,
    CompareRequest,
    JobOut,
    MultiCompareOut,
    TrackAnalysisOut,
    TrackOverrideIn,
    TrackOverrideOut,
)
from backend.cli.compare import _load_snapshot, build_diff_markdown
from backend.db import init_db, make_session_factory
from backend.domain.models import (
    Playlist,
    PlaylistPattern,
    PlaylistTrack,
    Track,
    TrackAnalysis,
    TrackOverride,
)
from backend.infrastructure.settings_store import load_settings
from backend.local_projects import brief_filename
from backend.report_generator import generate_brief
from backend.report_generator.pdf import generate_pdf_from_url
from backend.services.multi_compare import build_multi_compare
from backend.services.source_loader import load_pattern_source
from backend.services.track_overrides import (
    propagate_override_to_active_sessions,
    regenerate_playlist_patterns_for_track,
)

StyleKey = Literal["editorial", "soft", "newspaper", "blueprint"]
_VALID_STYLES: frozenset[str] = frozenset(("editorial", "soft", "newspaper", "blueprint"))

router = APIRouter(tags=["reports"])

SessionDep = Annotated[Session, Depends(get_session)]
DataDirDep = Annotated[Path, Depends(get_data_dir)]
QueueDep = Annotated[JobQueue, Depends(get_job_queue)]


@router.get("/playlists/{spotify_id}/brief", response_model=BriefOut)
def get_brief(
    spotify_id: str,
    session: SessionDep,
    data_dir: DataDirDep,
    regenerate: bool = False,
) -> BriefOut:
    """Renvoie le brief markdown d'une playlist.

    Cache fichier `data/reports/{spotify_id}.md`. Si présent et regenerate=false,
    lecture directe. Sinon, régénère depuis pattern le plus récent + features.
    """
    p = session.scalar(
        select(Playlist).where(Playlist.spotify_id == spotify_id),
    )
    if p is None:
        raise HTTPException(
            status_code=404, detail=f"Playlist {spotify_id!r} not found",
        )

    report_path = data_dir / "reports" / f"{brief_filename(spotify_id)}.md"

    if report_path.exists() and not regenerate:
        return BriefOut(
            spotify_id=spotify_id,
            playlist_name=p.name,
            markdown=report_path.read_text(encoding="utf-8"),
            generated_at=datetime.fromtimestamp(
                report_path.stat().st_mtime, tz=UTC,
            ),
            cached=True,
        )

    pat = session.scalar(
        select(PlaylistPattern)
        .where(PlaylistPattern.playlist_id == p.id)
        .order_by(PlaylistPattern.id.desc()),
    )
    if pat is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No pattern for playlist {spotify_id!r}. "
                "Run an analyze first."
            ),
        )

    pt_rows = session.scalars(
        select(PlaylistTrack)
        .where(PlaylistTrack.playlist_id == p.id)
        .order_by(PlaylistTrack.position),
    ).all()

    tracks_data: list[dict] = []
    for pt in pt_rows:
        latest = session.scalar(
            select(TrackAnalysis)
            .where(TrackAnalysis.track_id == pt.track_id)
            .order_by(TrackAnalysis.id.desc()),
        )
        if latest is None:
            continue
        tracks_data.append({
            "artist": pt.track.artist,
            "title": pt.track.title,
            "features": latest.features_json,
        })

    markdown = generate_brief(
        pat.pattern_json,
        playlist_name=p.name,
        tracks_data=tracks_data,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8")

    return BriefOut(
        spotify_id=spotify_id,
        playlist_name=p.name,
        markdown=markdown,
        generated_at=datetime.now(UTC),
        cached=False,
    )


@router.get("/playlists/{spotify_id}/brief.md")
def get_brief_md(
    spotify_id: str,
    session: SessionDep,
    data_dir: DataDirDep,
    regenerate: bool = False,
) -> Response:
    """Export markdown brut (téléchargement). Cache fichier puis fallback régénération.

    Réutilise la même logique que `get_brief()` mais retourne en download
    `text/markdown` avec Content-Disposition attachment. Utile pour archiver
    le brief sur disque ou le donner à un LLM externe.
    """
    p = session.scalar(
        select(Playlist).where(Playlist.spotify_id == spotify_id),
    )
    if p is None:
        raise HTTPException(
            status_code=404, detail=f"Playlist {spotify_id!r} not found",
        )

    report_path = data_dir / "reports" / f"{brief_filename(spotify_id)}.md"
    if report_path.exists() and not regenerate:
        content = report_path.read_text(encoding="utf-8")
    else:
        pat = session.scalar(
            select(PlaylistPattern)
            .where(PlaylistPattern.playlist_id == p.id)
            .order_by(PlaylistPattern.id.desc()),
        )
        if pat is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"No pattern for playlist {spotify_id!r}. "
                    "Run an analyze first."
                ),
            )
        pt_rows = session.scalars(
            select(PlaylistTrack)
            .where(PlaylistTrack.playlist_id == p.id)
            .order_by(PlaylistTrack.position),
        ).all()
        tracks_data: list[dict] = []
        for pt in pt_rows:
            latest = session.scalar(
                select(TrackAnalysis)
                .where(TrackAnalysis.track_id == pt.track_id)
                .order_by(TrackAnalysis.id.desc()),
            )
            if latest is None:
                continue
            tracks_data.append({
                "artist": pt.track.artist,
                "title": pt.track.title,
                "features": latest.features_json,
            })
        content = generate_brief(
            pat.pattern_json,
            playlist_name=p.name,
            tracks_data=tracks_data,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(content, encoding="utf-8")

    filename = f"{spotify_id}-brief.md"
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/playlists/{spotify_id}/brief.pdf")
def get_brief_pdf(
    spotify_id: str,
    session: SessionDep,
    data_dir: DataDirDep,
    request: Request,
    style: str = "editorial",
) -> Response:
    """Génère un PDF du brief via Chromium headless.

    Ouvre la page `/playlists/{id}/styles?style={style}` dans un Chromium
    headless et utilise --print-to-pdf. Fidélité 100% au rendu web, charts
    Chart.js inclus, taille typique 1-3 MB.
    """
    if style not in _VALID_STYLES:
        raise HTTPException(
            status_code=400,
            detail=f"Style {style!r} invalide. Valeurs : {sorted(_VALID_STYLES)}",
        )

    p = session.scalar(select(Playlist).where(Playlist.spotify_id == spotify_id))
    if p is None:
        raise HTTPException(status_code=404, detail=f"Playlist {spotify_id!r} not found")

    # URL self-reference. request.url.netloc inclut host:port — sur uvicorn local
    # c'est 127.0.0.1:8000 typiquement, accessible depuis Chromium headless.
    target_url = (
        f"{request.url.scheme}://{request.url.netloc}"
        f"/playlists/{spotify_id}/styles?style={style}"
    )
    pdf_path = (
        data_dir / "reports" / f"{brief_filename(spotify_id)}-{style}.pdf"
    )
    try:
        generate_pdf_from_url(target_url, pdf_path)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    content = pdf_path.read_bytes()
    filename = f"{spotify_id}-brief-{style}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/compare", response_model=CompareOut)
def compare(payload: CompareRequest) -> CompareOut:
    """Diff markdown entre 2 playlists déjà analysées."""
    engine = init_db()
    SessionFactory = make_session_factory(engine)
    with SessionFactory() as session:
        a = _load_snapshot(session, payload.id_a, pattern_id=payload.pattern_a)
        b = _load_snapshot(session, payload.id_b, pattern_id=payload.pattern_b)
        if a is None:
            raise HTTPException(
                status_code=404,
                detail=f"Playlist A {payload.id_a!r} not in DB",
            )
        if b is None:
            raise HTTPException(
                status_code=404,
                detail=f"Playlist B {payload.id_b!r} not in DB",
            )
        markdown = build_diff_markdown(a, b)

    return CompareOut(
        id_a=payload.id_a,
        id_b=payload.id_b,
        name_a=a.name,
        name_b=b.name,
        n_tracks_a=a.n_tracks,
        n_tracks_b=b.n_tracks,
        markdown=markdown,
        generated_at=datetime.now(UTC),
    )


_MULTI_COMPARE_MIN = 2
_MULTI_COMPARE_MAX = 5


@router.get("/compare/multi", response_model=MultiCompareOut)
def compare_multi(
    session: SessionDep,
    ids: Annotated[str, Query(description="Comma-separated list of 2-5 IDs")],
) -> MultiCompareOut:
    """Comparaison N-way (2-5 sources) : radar spectral + table stats.

    Chaque ID peut être un playlist_spotify_id, track_spotify_id ou `preset:KEY`.
    """
    id_list = [s.strip() for s in ids.split(",") if s.strip()]
    if not (_MULTI_COMPARE_MIN <= len(id_list) <= _MULTI_COMPARE_MAX):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Multi-compare requires {_MULTI_COMPARE_MIN}-{_MULTI_COMPARE_MAX} "
                f"sources, got {len(id_list)}"
            ),
        )
    if len(set(id_list)) != len(id_list):
        raise HTTPException(status_code=400, detail="Duplicate IDs in compare list")

    sources = [load_pattern_source(session, sid) for sid in id_list]
    result = build_multi_compare(sources)
    return MultiCompareOut(
        sources=result.sources,
        spectral_radar=result.spectral_radar,
        stats_table=result.stats_table,
    )


@router.get(
    "/tracks/{spotify_id}/analysis", response_model=TrackAnalysisOut,
)
def get_track_analysis(
    spotify_id: str, session: SessionDep,
) -> TrackAnalysisOut:
    """Renvoie la dernière analyse audio d'une track + meta Spotify."""
    track = session.scalar(
        select(Track).where(Track.spotify_id == spotify_id),
    )
    if track is None:
        raise HTTPException(
            status_code=404, detail=f"Track {spotify_id!r} not found",
        )
    latest = session.scalar(
        select(TrackAnalysis)
        .where(TrackAnalysis.track_id == track.id)
        .order_by(TrackAnalysis.id.desc()),
    )
    if latest is None:
        raise HTTPException(
            status_code=409,
            detail=f"No analysis for track {spotify_id!r}",
        )
    return TrackAnalysisOut(
        spotify_id=track.spotify_id,
        title=track.title,
        artist=track.artist,
        duration_ms=track.duration_ms,
        release_date=track.release_date,
        audio_path=latest.audio_path,
        analyzer_version=latest.analyzer_version,
        features=latest.features_json,
        analyzed_at=latest.created_at,
    )


@router.patch(
    "/tracks/{spotify_id}/overrides", response_model=TrackOverrideOut,
)
def upsert_track_override(
    spotify_id: str,
    payload: TrackOverrideIn,
    session: SessionDep,
    data_dir: DataDirDep,
) -> TrackOverrideOut:
    """Crée ou met à jour la correction manuelle d'une track (BPM/key/mode).

    Partial update : seuls les champs fournis (non-null) sont écrits.
    Pour reset un champ spécifique, utilise DELETE.

    Régénère automatiquement le pattern de toutes les playlists contenant
    cette track + invalide les briefs en cache.
    """
    track = session.scalar(
        select(Track).where(Track.spotify_id == spotify_id),
    )
    if track is None:
        raise HTTPException(
            status_code=404, detail=f"Track {spotify_id!r} introuvable",
        )

    override = session.scalar(
        select(TrackOverride).where(TrackOverride.track_id == track.id),
    )
    if override is None:
        override = TrackOverride(track_id=track.id)
        session.add(override)

    if payload.bpm is not None:
        override.bpm = float(payload.bpm)
    if payload.key_note is not None:
        override.key_note = payload.key_note
    if payload.key_mode is not None:
        override.key_mode = payload.key_mode

    session.commit()
    session.refresh(override)
    regenerate_playlist_patterns_for_track(session, track.id, data_dir)
    propagate_override_to_active_sessions(session, track, data_dir)
    session.commit()
    return TrackOverrideOut(
        bpm=override.bpm,
        key_note=override.key_note,
        key_mode=override.key_mode,
    )


@router.delete("/tracks/{spotify_id}/overrides", status_code=204)
def delete_track_override(
    spotify_id: str,
    session: SessionDep,
    data_dir: DataDirDep,
) -> None:
    """Supprime entièrement l'override d'une track (reset to algos).

    Régénère le pattern des playlists impactées + invalide les briefs cachés.
    """
    track = session.scalar(
        select(Track).where(Track.spotify_id == spotify_id),
    )
    if track is None:
        raise HTTPException(
            status_code=404, detail=f"Track {spotify_id!r} introuvable",
        )
    override = session.scalar(
        select(TrackOverride).where(TrackOverride.track_id == track.id),
    )
    if override is not None:
        session.delete(override)
        session.commit()
        regenerate_playlist_patterns_for_track(session, track.id, data_dir)
        propagate_override_to_active_sessions(session, track, data_dir)
        session.commit()


@router.post("/tracks/analyze", response_model=JobOut, status_code=202)
async def trigger_track_analyze(
    payload: AnalyzeTrackRequest, queue: QueueDep,
) -> JobOut:
    """Crée un job pour analyser une track Spotify isolée (hors playlist).

    La track est téléchargée via YouTube puis analysée, et persistée en DB
    comme `Track` + `TrackAnalysis` — sans entrée `PlaylistTrack` (donc pas
    rattachée à une playlist). Utile comme cible de session guidée ou de
    plan d'action.
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

    job = queue.create("track-analyze")
    task = asyncio.create_task(
        run_track_analyze_job(queue, job.id, payload),
        name=f"track-analyze:{job.id}",
    )
    queue.attach_task(job.id, task)
    return JobOut(**job.to_dict())
