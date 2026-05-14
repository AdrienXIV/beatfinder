"""Pipeline d'analyse d'une track Spotify isolée (hors playlist).

Symétrique de `cli/pipeline.py` mais pour une seule track : pas de playlist
agrégée, pas de pattern, juste `Track` + `TrackAnalysis` en DB. Permet
d'utiliser une track Spotify isolée comme cible de plan d'action ou de session
guidée.

Réutilisable depuis CLI et FastAPI via callbacks `on_progress` / `on_log`.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from backend.analyzers import analyze_track
from backend.config import get_settings
from backend.db import init_db, make_session_factory
from backend.domain.models import Track, TrackAnalysis
from backend.infrastructure.audio_sources import AudioSourceError, YouTubeSource
from backend.infrastructure.spotify_client import SpotifyClient
from backend.types import LogCallback, ProgressCallback


def run_track_pipeline(
    track_url: str,
    *,
    on_progress: ProgressCallback | None = None,
    on_log: LogCallback | None = None,
) -> dict[str, Any]:
    """Analyse une track Spotify isolée et la persiste en DB.

    Étapes :
      1. Parse l'URL + récupère les métadonnées Spotify.
      2. Télécharge l'audio via YouTube (yt-dlp).
      3. Analyse audio complète (BPM, tonalité, énergie, spectral, structure, timbre).
      4. Upsert `Track` + insertion d'une nouvelle `TrackAnalysis`.

    Returns: dict {track_spotify_id, title, artist, features, audio_path}.
    """
    log = logging.getLogger("backend.cli.track_pipeline")

    def _progress(current: float, total: int, label: str = "") -> None:
        if on_progress is not None:
            try:
                on_progress(current, total, label)
            except Exception:  # noqa: BLE001
                log.warning("on_progress callback raised", exc_info=True)

    def _emit(line: str) -> None:
        log.info(line)
        if on_log is not None:
            try:
                on_log(line)
            except Exception:  # noqa: BLE001
                log.warning("on_log callback raised", exc_info=True)

    _emit(f"Fetching track metadata: {track_url}")
    _progress(0, 1, "Métadonnées Spotify…")

    client = SpotifyClient()
    meta = client.get_track_meta(track_url)
    track_lbl = f"{meta.artist} — {meta.title}"[:80]
    _emit(f"Track : {track_lbl} ({meta.duration_ms / 1000:.0f}s)")

    settings = get_settings()
    cache_dir = settings.data_dir / "audio"
    yt = YouTubeSource(
        cache_dir=cache_dir,
        cookies_file=settings.yt_dlp_cookies_file,
    )

    _emit(f"  → download YouTube : {track_lbl}")
    _progress(0.1, 1, f"Téléchargement : {track_lbl}")
    try:
        audio_path = yt.download(
            spotify_id=meta.spotify_id,
            title=meta.title,
            artist=meta.artist,
            duration_ms=meta.duration_ms,
        )
    except AudioSourceError as exc:
        _emit(f"  ! échec du téléchargement : {exc}")
        raise

    def _on_step(step_key: str, step_label: str, fraction: float) -> None:
        # Mappe la fraction [0, 1] de l'analyse à [0.3, 0.95] du total job.
        current = 0.3 + fraction * 0.65
        _progress(current, 1, f"{step_label} : {track_lbl}")

    _emit(f"  → analyse audio : {track_lbl}")
    features = analyze_track(audio_path, on_step=_on_step, on_log=_emit)
    _emit(f"  ✓ analyse OK : {track_lbl}")

    _progress(0.95, 1, "Persistance DB…")
    engine = init_db()
    Session = make_session_factory(engine)
    with Session() as session:
        track_db = session.scalar(
            select(Track).where(Track.spotify_id == meta.spotify_id),
        )
        if track_db is None:
            track_db = Track(
                spotify_id=meta.spotify_id,
                title=meta.title,
                artist=meta.artist,
                duration_ms=meta.duration_ms,
                release_date=meta.release_date,
            )
            session.add(track_db)
        else:
            track_db.title = meta.title
            track_db.artist = meta.artist
            track_db.duration_ms = meta.duration_ms
            track_db.release_date = meta.release_date
        session.flush()

        session.add(
            TrackAnalysis(
                track_id=track_db.id,
                features_json=features,
                audio_path=str(audio_path),
            ),
        )
        session.commit()

    _progress(1, 1, f"Terminé : {track_lbl}")
    return {
        "track_spotify_id": meta.spotify_id,
        "title": meta.title,
        "artist": meta.artist,
        "duration_ms": meta.duration_ms,
        "features": features,
        "audio_path": str(audio_path),
    }
