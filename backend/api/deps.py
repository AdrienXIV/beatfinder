"""FastAPI dependencies — DB session, data_dir et JobQueue tirés du app.state.

Tout ce qui dépend de l'état initialisé dans `lifespan` passe par ici. Permet
de remplacer ces deps en test sans toucher le wiring du code applicatif.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session

from backend.api.jobs import JobQueue


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    with factory() as session:
        yield session


def get_data_dir(request: Request) -> Path:
    return request.app.state.data_dir


def get_job_queue(request: Request) -> JobQueue:
    return request.app.state.job_queue
