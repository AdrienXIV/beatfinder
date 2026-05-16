"""Schemas pour la JobQueue + déclencheur d'analyse playlist."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ._datetime import UtcDatetime


class JobProgressOut(BaseModel):
    current: float = 0.0
    total: int = 0
    label: str = ""


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: JobProgressOut
    log: list[str]
    result: dict[str, Any] | None = None
    error: str | None = None
    revision: int
    created_at: UtcDatetime
    updated_at: UtcDatetime


class AnalyzeRequest(BaseModel):
    url: str = Field(description="URL/URI/ID Spotify d'une playlist")
    save: bool = Field(default=True, description="Persister en DB après analyse")
    limit: int | None = Field(default=None, description="Limiter à N tracks")
    download: bool = Field(
        default=True, description="DL audio via YouTube si manquant",
    )


class AnalyzeTrackRequest(BaseModel):
    url: str = Field(description="URL/URI/ID Spotify d'une track isolée")
