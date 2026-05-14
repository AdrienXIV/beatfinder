"""Job runner — exécute les pipelines longs dans un thread + reporte progression.

Sépare la queue (jobs.py = état mutable) du runner (ici = orchestration async).
"""
from __future__ import annotations

import asyncio
import logging

from backend.api.jobs import JobQueue
from backend.api.schemas import AnalyzeRequest, AnalyzeTrackRequest
from backend.cli.pipeline import run_pipeline
from backend.cli.track_pipeline import run_track_pipeline
from backend.local_projects import run_local_pipeline

log = logging.getLogger("backend.api.job_runner")


async def run_local_analyze_job(
    queue: JobQueue,
    job_id: str,
    project_spotify_id: str,
    mode: str = "new",
) -> None:
    """Analyse les tracks d'un project local (skip Spotify+YouTube).

    mode="new"  : skip les tracks déjà analysées, charge leurs features du cache DB
    mode="full" : re-analyse toutes les tracks (utile après modif fichier audio)
    """
    queue.mark_running(job_id)
    queue.log(
        job_id,
        f"Starting local analyze (mode={mode}): {project_spotify_id}",
    )

    def on_progress(current: int, total: int, label: str) -> None:
        queue.set_progress(job_id, current, total, label)

    def on_log(line: str) -> None:
        queue.log(job_id, line)

    try:
        result = await asyncio.to_thread(
            run_local_pipeline,
            project_spotify_id,
            mode=mode,
            on_progress=on_progress,
            on_log=on_log,
        )
    except asyncio.CancelledError:
        queue.log(job_id, "Cancelled by user.")
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Local analyze job %s failed", job_id)
        queue.mark_error(job_id, f"{type(exc).__name__}: {exc}")
        return

    queue.mark_done(job_id, {
        "playlist_spotify_id": result.get("playlist_spotify_id"),
        "mode": result.get("mode"),
        "n_tracks": len(result.get("tracks", [])),
        "n_analyzed": result.get("n_analyzed"),
        "n_reused": result.get("n_reused"),
        "report_path": result.get("report_path"),
    })


async def run_analyze_job(
    queue: JobQueue, job_id: str, payload: AnalyzeRequest,
) -> None:
    """Exécute le pipeline d'analyse dans un thread, reporte via callbacks."""
    queue.mark_running(job_id)
    queue.log(job_id, f"Starting analyze: {payload.url}")

    def on_progress(current: int, total: int, label: str) -> None:
        queue.set_progress(job_id, current, total, label)

    def on_log(line: str) -> None:
        queue.log(job_id, line)

    try:
        result = await asyncio.to_thread(
            run_pipeline,
            payload.url,
            save=payload.save,
            limit=payload.limit,
            download=payload.download,
            analyze=True,
            on_progress=on_progress,
            on_log=on_log,
        )
    except asyncio.CancelledError:
        queue.log(job_id, "Cancelled by user.")
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Analyze job %s failed", job_id)
        queue.mark_error(job_id, f"{type(exc).__name__}: {exc}")
        return

    skipped = result.get("skipped", []) or []
    queue.mark_done(job_id, {
        "playlist_spotify_id": result.get("playlist_spotify_id"),
        "n_tracks": len(result.get("tracks", [])),
        "n_analyzed": sum(
            1 for t in result.get("tracks", []) if "features" in t
        ),
        "n_skipped": len(skipped),
        "skipped": skipped,
        "report_path": result.get("report_path"),
        "saved": payload.save,
    })


async def run_track_analyze_job(
    queue: JobQueue, job_id: str, payload: AnalyzeTrackRequest,
) -> None:
    """Analyse une track Spotify isolée. Persiste Track + TrackAnalysis."""
    queue.mark_running(job_id)
    queue.log(job_id, f"Starting track analyze: {payload.url}")

    def on_progress(current: float, total: int, label: str) -> None:
        queue.set_progress(job_id, current, total, label)

    def on_log(line: str) -> None:
        queue.log(job_id, line)

    try:
        result = await asyncio.to_thread(
            run_track_pipeline,
            payload.url,
            on_progress=on_progress,
            on_log=on_log,
        )
    except asyncio.CancelledError:
        queue.log(job_id, "Cancelled by user.")
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Track analyze job %s failed", job_id)
        queue.mark_error(job_id, f"{type(exc).__name__}: {exc}")
        return

    queue.mark_done(job_id, {
        "track_spotify_id": result.get("track_spotify_id"),
        "title": result.get("title"),
        "artist": result.get("artist"),
        "duration_ms": result.get("duration_ms"),
    })
