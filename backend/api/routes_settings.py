"""Routes FastAPI cache + settings (V1.7).

  GET    /cache/stats                tailles + counts par catégorie
  DELETE /cache/{kind}                flush youtube|local-audio|reports|actions
  GET    /settings/status             flags simples (Spotify configuré ?)
  GET    /settings/spotify            credentials Spotify (secret jamais renvoyé)
  PUT    /settings/spotify            save credentials
  DELETE /settings/spotify            clear credentials
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_data_dir, get_session
from backend.api.schemas import (
    AppStatusOut,
    CacheFlushOut,
    CacheStatsOut,
    SpotifySettingsIn,
    SpotifySettingsOut,
)
from backend.infrastructure.settings_store import (
    SpotifyCreds,
    clear_spotify,
    load_settings,
    save_spotify,
)
from backend.services.cache_inspector import FLUSHABLE, flush_cache, get_cache_stats

log = logging.getLogger("backend.api.routes_settings")

router = APIRouter(tags=["settings"])

DataDirDep = Annotated[Path, Depends(get_data_dir)]
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/cache/stats", response_model=CacheStatsOut)
def get_cache_stats_route(data_dir: DataDirDep, session: SessionDep) -> CacheStatsOut:
    raw = get_cache_stats(data_dir, session)
    return CacheStatsOut(**raw)


@router.delete("/cache/{kind}", response_model=CacheFlushOut)
def delete_cache(kind: str, data_dir: DataDirDep) -> CacheFlushOut:
    if kind not in FLUSHABLE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot flush cache {kind!r}. Allowed: {list(FLUSHABLE)}",
        )
    result = flush_cache(kind, data_dir)  # type: ignore[arg-type]
    return CacheFlushOut(**result)


def _to_out(creds: SpotifyCreds) -> SpotifySettingsOut:
    return SpotifySettingsOut(
        client_id=creds.client_id,
        redirect_uri=creds.redirect_uri,
        has_secret=bool(creds.client_secret),
        is_configured=creds.is_configured,
    )


@router.get("/settings/status", response_model=AppStatusOut)
def get_status(data_dir: DataDirDep) -> AppStatusOut:
    """Status léger pour le frontend (banners de config manquante)."""
    s = load_settings(data_dir)
    return AppStatusOut(spotify_configured=s.spotify.is_configured)


@router.get("/settings/spotify", response_model=SpotifySettingsOut)
def get_spotify_settings(data_dir: DataDirDep) -> SpotifySettingsOut:
    s = load_settings(data_dir)
    return _to_out(s.spotify)


@router.put("/settings/spotify", response_model=SpotifySettingsOut)
def put_spotify_settings(
    payload: SpotifySettingsIn, data_dir: DataDirDep,
) -> SpotifySettingsOut:
    current = load_settings(data_dir)
    has_existing_secret = bool(current.spotify.client_secret)

    if not payload.client_id.strip():
        raise HTTPException(status_code=400, detail="client_id est requis")
    if not payload.client_secret.strip() and not has_existing_secret:
        raise HTTPException(
            status_code=400,
            detail="client_secret est requis pour la 1ère configuration",
        )

    creds = SpotifyCreds(
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        redirect_uri=payload.redirect_uri,
    )
    new = save_spotify(creds, data_dir)
    return _to_out(new.spotify)


@router.delete("/settings/spotify", response_model=SpotifySettingsOut)
def delete_spotify_settings(data_dir: DataDirDep) -> SpotifySettingsOut:
    new = clear_spotify(data_dir)
    return _to_out(new.spotify)
