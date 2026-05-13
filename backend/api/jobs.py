"""In-memory JobQueue pour analyses async.

Mono-user, V1 desktop. Pas de persistance — perdu au restart serveur.
Asyncio single-thread donc pas de lock nécessaire sur les ops dict.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class JobProgress:
    current: float = 0.0
    total: int = 0
    label: str = ""


@dataclass
class Job:
    id: str
    kind: str
    status: JobStatus = JobStatus.QUEUED
    progress: JobProgress = field(default_factory=JobProgress)
    log: deque[str] = field(default_factory=lambda: deque(maxlen=200))
    result: dict[str, Any] | None = None
    error: str | None = None
    revision: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    task: asyncio.Task | None = None

    def _bump(self) -> None:
        self.revision += 1
        self.updated_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status.value,
            "progress": {
                "current": self.progress.current,
                "total": self.progress.total,
                "label": self.progress.label,
            },
            "log": list(self.log),
            "result": self.result,
            "error": self.error,
            "revision": self.revision,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class JobQueue:
    """Mono-process in-memory queue. Pas thread-safe — usage asyncio only."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, kind: str) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, kind=kind)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        return sorted(
            self._jobs.values(), key=lambda j: j.created_at, reverse=True,
        )

    def set_progress(
        self, job_id: str, current: float, total: int, label: str = "",
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.progress.current = float(current)
        job.progress.total = total
        if label:
            job.progress.label = label
        job._bump()

    def log(self, job_id: str, line: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        # Heure locale (machine) : plus parlante côté utilisateur que UTC
        ts = datetime.now().strftime("%H:%M:%S")
        job.log.append(f"[{ts}] {line}")
        job._bump()

    def mark_running(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = JobStatus.RUNNING
        job._bump()

    def mark_done(self, job_id: str, result: dict[str, Any]) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = JobStatus.DONE
        job.result = result
        job._bump()

    def mark_error(self, job_id: str, error: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = JobStatus.ERROR
        job.error = error
        job._bump()

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.task is None:
            return False
        job.task.cancel()
        job.status = JobStatus.CANCELLED
        job._bump()
        return True

    def attach_task(self, job_id: str, task: asyncio.Task) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            job.task = task
