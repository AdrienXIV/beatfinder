"""Schemas transverses : health, status, cache, settings Spotify."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HealthOut(BaseModel):
    status: str
    version: str
    data_dir: str


class AppStatusOut(BaseModel):
    spotify_configured: bool


class DBCountsOut(BaseModel):
    playlists: int
    tracks: int
    playlist_tracks: int
    analyses: int
    patterns: int


class CacheCategoryOut(BaseModel):
    kind: str
    label: str
    description: str
    n_files: int
    size_bytes: int
    flushable: bool
    counts: DBCountsOut | None = None


class CacheStatsOut(BaseModel):
    youtube: CacheCategoryOut
    local_audio: CacheCategoryOut = Field(alias="local-audio")
    reports: CacheCategoryOut
    actions: CacheCategoryOut
    db: CacheCategoryOut

    model_config = ConfigDict(populate_by_name=True)


class CacheFlushOut(BaseModel):
    kind: str
    n_files_deleted: int
    bytes_freed: int


class SpotifySettingsOut(BaseModel):
    """Retourné par GET /settings/spotify. Le secret n'est jamais renvoyé en clair."""
    client_id: str = ""
    redirect_uri: str = ""
    has_secret: bool = False
    is_configured: bool = False


class SpotifySettingsIn(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: str = ""
