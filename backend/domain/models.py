"""SQLAlchemy 2.0 models — Playlist, Track, PlaylistTrack, TrackAnalysis, PlaylistPattern."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now_utc() -> datetime:
    return datetime.now(UTC)


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_id: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(default="")
    owner_display_name: Mapped[str | None] = mapped_column(default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=_now_utc, onupdate=_now_utc)

    tracks: Mapped[list[PlaylistTrack]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan",
    )
    patterns: Mapped[list[PlaylistPattern]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan",
    )


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_id: Mapped[str] = mapped_column(unique=True, index=True)
    title: Mapped[str]
    artist: Mapped[str]
    duration_ms: Mapped[int]
    release_date: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=_now_utc)

    analyses: Mapped[list[TrackAnalysis]] = relationship(
        back_populates="track", cascade="all, delete-orphan",
    )


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id"), primary_key=True,
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id"), primary_key=True,
    )
    position: Mapped[int] = mapped_column(default=0)

    playlist: Mapped[Playlist] = relationship(back_populates="tracks")
    track: Mapped[Track] = relationship()


class TrackAnalysis(Base):
    __tablename__ = "track_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    features_json: Mapped[dict] = mapped_column(JSON)
    audio_path: Mapped[str | None] = mapped_column(default=None)
    analyzer_version: Mapped[str] = mapped_column(default="v1")
    created_at: Mapped[datetime] = mapped_column(default=_now_utc)

    track: Mapped[Track] = relationship(back_populates="analyses")


class PlaylistPattern(Base):
    __tablename__ = "playlist_patterns"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id"), index=True,
    )
    pattern_json: Mapped[dict] = mapped_column(JSON)
    n_tracks_analyzed: Mapped[int] = mapped_column(default=0)
    analyzer_version: Mapped[str] = mapped_column(default="v1")
    created_at: Mapped[datetime] = mapped_column(default=_now_utc)

    playlist: Mapped[Playlist] = relationship(back_populates="patterns")
