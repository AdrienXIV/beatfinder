"""Routes FastAPI projects (feature D : upload + analyse de fichiers locaux).

  POST /projects                          : crée un project local vide
  POST /projects/{spotify_id}/tracks      : upload multipart N fichiers audio
  POST /projects/{spotify_id}/analyze     : lance un job d'analyse local
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import Response
from pydantic import BaseModel

from backend.api.deps import get_job_queue
from backend.api.job_runner import run_local_analyze_job
from backend.api.jobs import JobQueue
from backend.api.schemas import JobOut
from backend.local_projects import (
    ALLOWED_EXTENSIONS,
    add_tracks,
    create_project,
    delete_project,
    is_local_playlist,
)

log = logging.getLogger("backend.api.routes_projects")

router = APIRouter(prefix="/projects", tags=["projects"])

QueueDep = Annotated[JobQueue, Depends(get_job_queue)]


class CreateProjectRequest(BaseModel):
    name: str
    owner_display_name: str | None = None


class CreateProjectOut(BaseModel):
    spotify_id: str
    name: str
    owner_display_name: str | None


class AddedTrackOut(BaseModel):
    spotify_id: str
    title: str
    artist: str
    duration_ms: int
    audio_path: str
    filename: str


@router.post("", response_model=CreateProjectOut, status_code=201)
async def create_project_endpoint(
    payload: CreateProjectRequest,
) -> CreateProjectOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    project = create_project(
        name=name, owner_display_name=payload.owner_display_name,
    )
    return CreateProjectOut(
        spotify_id=project["spotify_id"],
        name=project["name"],
        owner_display_name=project["owner_display_name"],
    )


@router.post("/{spotify_id}/tracks", response_model=list[AddedTrackOut])
async def upload_tracks(
    spotify_id: str,
    files: list[UploadFile] = File(...),
    overrides_json: str | None = Form(default=None),
) -> list[AddedTrackOut]:
    """Upload N audio files. ID3 tags lus automatiquement, overrides en JSON."""
    if not is_local_playlist(spotify_id):
        raise HTTPException(
            status_code=400, detail="Not a local project (use /api/playlists/analyze for Spotify)",
        )
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    overrides: dict[str, dict[str, str]] = {}
    if overrides_json:
        try:
            overrides = json.loads(overrides_json)
            if not isinstance(overrides, dict):
                raise ValueError("must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid overrides_json: {exc}",
            ) from exc

    file_blobs: list[tuple[str, bytes]] = []
    skipped: list[str] = []
    for f in files:
        filename = f.filename or ""
        ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            skipped.append(filename)
            continue
        content = await f.read()
        file_blobs.append((filename, content))

    if not file_blobs:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No valid audio files. Accepted: {sorted(ALLOWED_EXTENSIONS)}. "
                f"Skipped: {skipped}"
            ),
        )

    try:
        added = add_tracks(spotify_id, file_blobs, overrides=overrides)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [AddedTrackOut(**t) for t in added]


@router.post(
    "/{spotify_id}/analyze", response_model=JobOut, status_code=202,
)
async def trigger_local_analyze(
    spotify_id: str,
    queue: QueueDep,
    mode: Annotated[
        Literal["new", "full"],
        Query(description="'new' réutilise le cache d'analyses, 'full' re-analyse tout"),
    ] = "new",
) -> JobOut:
    """Spawn job d'analyse sur les tracks audio uploadées.

    mode=new  (default) : skip les tracks déjà analysées, juste les nouvelles
    mode=full           : re-analyse tout (utile si tu as remplacé un fichier audio)
    """
    if not is_local_playlist(spotify_id):
        raise HTTPException(
            status_code=400, detail="Not a local project",
        )
    job = queue.create(f"analyze_local_{mode}")
    task = asyncio.create_task(
        run_local_analyze_job(queue, job.id, spotify_id, mode=mode),
        name=f"analyze_local:{job.id}",
    )
    queue.attach_task(job.id, task)
    return JobOut(**job.to_dict())


@router.delete("/{spotify_id}", status_code=204)
async def delete_project_endpoint(spotify_id: str) -> Response:
    """Supprime le project local + tracks + analyses + pattern + fichiers audio."""
    if not is_local_playlist(spotify_id):
        raise HTTPException(
            status_code=400, detail="Not a local project",
        )
    try:
        result = delete_project(spotify_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log.info("Deleted project %s: %s", spotify_id, result)
    return Response(status_code=204)
