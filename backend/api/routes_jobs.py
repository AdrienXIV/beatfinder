"""Routes FastAPI jobs (sprint 3b étape 3).

  GET  /jobs                       : liste jobs en cours / récents
  GET  /jobs/{job_id}              : état courant d'un job
  GET  /jobs/{job_id}/stream       : SSE — push events à chaque révision
  POST /jobs/{job_id}/cancel       : cancel un job en cours
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.api.deps import get_job_queue
from backend.api.jobs import JobQueue, JobStatus
from backend.api.schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

QueueDep = Annotated[JobQueue, Depends(get_job_queue)]

SSE_POLL_INTERVAL = 0.5
SSE_HEARTBEAT_INTERVAL = 15.0


@router.get("", response_model=list[JobOut])
def list_jobs(queue: QueueDep) -> list[JobOut]:
    return [JobOut(**j.to_dict()) for j in queue.list_jobs()]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, queue: QueueDep) -> JobOut:
    job = queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return JobOut(**job.to_dict())


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, queue: QueueDep) -> JobOut:
    job = queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} already {job.status.value}",
        )
    queue.cancel(job_id)
    return JobOut(**queue.get(job_id).to_dict())


def _sse_event(event: str, data: object) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode()


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, queue: QueueDep) -> StreamingResponse:
    """Server-Sent Events : push état du job à chaque révision + heartbeat."""
    job = queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    async def event_stream() -> AsyncIterator[bytes]:
        last_revision = -1
        last_heartbeat = asyncio.get_event_loop().time()

        # Initial snapshot
        current = queue.get(job_id)
        if current is not None:
            last_revision = current.revision
            yield _sse_event("update", current.to_dict())

        while True:
            current = queue.get(job_id)
            if current is None:
                yield _sse_event("error", {"detail": "job vanished"})
                return

            now = asyncio.get_event_loop().time()
            if current.revision > last_revision:
                last_revision = current.revision
                yield _sse_event("update", current.to_dict())
                last_heartbeat = now
            elif now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL:
                yield b": heartbeat\n\n"
                last_heartbeat = now

            if current.status in (
                JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELLED,
            ):
                yield _sse_event(current.status.value, current.to_dict())
                return

            await asyncio.sleep(SSE_POLL_INTERVAL)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
