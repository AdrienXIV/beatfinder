"""SQLAlchemy 2.0 models.

Entités principales :
- Playlist / Track / PlaylistTrack / TrackAnalysis / PlaylistPattern
  → flow d'analyse standard (Spotify ou projet local).
- CreativeSession / SessionVersion
  → flow "session guidée" : compare itérativement une prod en cours à une cible
  d'inspiration figée. Chaque version est analysée indépendamment, sans
  moyennage avec les précédentes.
"""
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


class TrackOverride(Base):
    """Correction manuelle utilisateur des features mesurées par les algos.

    L'utilisateur peut surcharger BPM, note racine, et mode quand l'analyse
    audio est jugée fausse (cas d'ambiguïté triolet/half-time pour le tempo
    ou consensus 3-voters trompeur pour la tonalité). Une seule entrée par
    track : update ou clear.

    Note : c'est isolé de TrackAnalysis pour ne pas polluer l'analyse audio
    brute. Le helper `apply_overrides()` fusionne l'override sur les features
    au moment de la lecture.
    """

    __tablename__ = "track_overrides"

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id"), primary_key=True,
    )
    bpm: Mapped[float | None] = mapped_column(default=None)
    key_note: Mapped[str | None] = mapped_column(default=None)
    key_mode: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=_now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        default=_now_utc, onupdate=_now_utc,
    )

    track: Mapped[Track] = relationship()


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


class CreativeSession(Base):
    """Session guidée : démarrage from-scratch d'une track avec une cible figée.

    Le `target_pattern_json` est un snapshot du pattern cible au moment de la
    création de la session — il ne suit pas l'évolution de la playlist cible
    (qui pourrait être ré-analysée plus tard).

    `target_kind` détermine comment lire `target_ref` :
    - "spotify_playlist" / "local_playlist" : `target_ref` = playlists.spotify_id
    - "spotify_track" : `target_ref` = tracks.spotify_id
    - "upload" : `target_ref` = chemin local d'un fichier audio (Phase 2)
    """

    __tablename__ = "creative_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_id: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(default="")
    target_kind: Mapped[str]
    target_ref: Mapped[str]
    target_name: Mapped[str] = mapped_column(default="")
    target_pattern_json: Mapped[dict] = mapped_column(JSON)
    ambiance_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    plan_md: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(default=False)
    # État draft (False) → locked (True). Tant que draft, l'utilisateur peut
    # corriger les BPM/key de la cible, ajouter/modifier des tracks. Une fois
    # locked, la cible est figée et les versions peuvent être uploadées.
    is_locked: Mapped[bool] = mapped_column(default=False)
    locked_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=_now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=_now_utc, onupdate=_now_utc)

    versions: Mapped[list[SessionVersion]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionVersion.version_number",
    )


class SessionVersion(Base):
    """Une version d'une track en cours dans une CreativeSession.

    Chaque version est un upload audio indépendant — pas de moyennage avec les
    précédentes. Le `fit_score` mesure la convergence vers la cible figée de
    la session (% de features dans le p25-p75 du target_pattern).
    """

    __tablename__ = "session_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("creative_sessions.id"), index=True,
    )
    version_number: Mapped[int]
    name: Mapped[str] = mapped_column(default="")
    audio_path: Mapped[str]
    features_json: Mapped[dict] = mapped_column(JSON)
    fit_score: Mapped[float | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=_now_utc)

    session: Mapped[CreativeSession] = relationship(back_populates="versions")
