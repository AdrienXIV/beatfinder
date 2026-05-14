"""Pipeline d'analyse playlist Spotify — CLI + fonction réutilisable.

La logique métier est dans `run_pipeline()` pour être appelable depuis :
  - la CLI (`python -m backend.cli.pipeline …`)
  - les routes FastAPI (POST /api/playlists/analyze, via JobQueue + thread)

Usage CLI :
    python -m backend.cli.pipeline "<spotify_playlist_url>"
    python -m backend.cli.pipeline "<spotify_playlist_url>" --download --limit 3
    python -m backend.cli.pipeline "<spotify_playlist_url>" --analyze --limit 3
    python -m backend.cli.pipeline "<spotify_playlist_url>" --analyze --save
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select

from backend.analyzers import analyze_track
from backend.config import get_settings
from backend.db import init_db, make_session_factory
from backend.domain.models import (
    Playlist,
    PlaylistPattern,
    PlaylistTrack,
    Track,
    TrackAnalysis,
)
from backend.infrastructure.audio_sources import AudioSourceError, YouTubeSource
from backend.infrastructure.spotify_client import (
    EditorialPlaylistError,
    PlaylistAccessError,
    PlaylistMeta,
    SpotifyClient,
    TrackMeta,
)
from backend.report_generator import generate_brief
from backend.services.pattern_extractor import extract_pattern
from backend.types import LogCallback, ProgressCallback


def _setup_logging() -> None:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )


def _persist(
    log: logging.Logger,
    playlist_meta: PlaylistMeta,
    tracks: list[TrackMeta],
    track_rows: list[dict],
    pattern: dict | None,
) -> None:
    """Upsert playlist + tracks + analyses + pattern dans SQLite."""
    engine = init_db()
    Session = make_session_factory(engine)

    with Session() as session:
        playlist = session.scalar(
            select(Playlist).where(Playlist.spotify_id == playlist_meta.spotify_id)
        )
        if playlist:
            playlist.name = playlist_meta.name
            playlist.owner_display_name = playlist_meta.owner_display_name
            playlist.description = playlist_meta.description
        else:
            playlist = Playlist(
                spotify_id=playlist_meta.spotify_id,
                name=playlist_meta.name,
                owner_display_name=playlist_meta.owner_display_name,
                description=playlist_meta.description,
            )
            session.add(playlist)
        session.flush()

        for pos, t in enumerate(tracks):
            track_db = session.scalar(
                select(Track).where(Track.spotify_id == t.spotify_id)
            )
            if track_db:
                track_db.title = t.title
                track_db.artist = t.artist
                track_db.duration_ms = t.duration_ms
                track_db.release_date = t.release_date
            else:
                track_db = Track(
                    spotify_id=t.spotify_id,
                    title=t.title,
                    artist=t.artist,
                    duration_ms=t.duration_ms,
                    release_date=t.release_date,
                )
                session.add(track_db)
            session.flush()

            pt = session.scalar(
                select(PlaylistTrack).where(
                    PlaylistTrack.playlist_id == playlist.id,
                    PlaylistTrack.track_id == track_db.id,
                )
            )
            if pt:
                pt.position = pos
            else:
                session.add(
                    PlaylistTrack(
                        playlist_id=playlist.id,
                        track_id=track_db.id,
                        position=pos,
                    )
                )

        # Une nouvelle analyse par run (on garde l'historique pour comparer V1 / V1.5)
        for row in track_rows:
            if "features" not in row:
                continue
            track_db = session.scalar(
                select(Track).where(Track.spotify_id == row["spotify_id"])
            )
            if track_db is None:
                continue
            session.add(
                TrackAnalysis(
                    track_id=track_db.id,
                    features_json=row["features"],
                    audio_path=row.get("audio_path"),
                )
            )

        if pattern is not None:
            session.add(
                PlaylistPattern(
                    playlist_id=playlist.id,
                    pattern_json=pattern,
                    n_tracks_analyzed=int(pattern.get("n_tracks", 0)),
                )
            )

        session.commit()
        log.info(
            "Sauvegardé : playlist '%s' + %d tracks + pattern (%d analysés)",
            playlist_meta.name, len(tracks),
            pattern.get("n_tracks", 0) if pattern else 0,
        )


def run_pipeline(
    playlist_url: str,
    *,
    save: bool = False,
    limit: int | None = None,
    download: bool = True,
    analyze: bool = True,
    on_progress: ProgressCallback | None = None,
    on_log: LogCallback | None = None,
) -> dict[str, Any]:
    """Pipeline complet d'analyse playlist Spotify.

    Réutilisable depuis CLI et FastAPI. Les callbacks `on_progress` et `on_log`
    permettent de reporter la progression vers un consumer externe (JobQueue).
    """
    log = logging.getLogger("backend.cli.pipeline")

    def _progress(current: int, total: int, label: str = "") -> None:
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

    if save and not analyze:
        raise ValueError("save requires analyze")

    _emit(f"Fetching playlist tracks from Spotify: {playlist_url}")
    client = SpotifyClient()
    tracks = client.get_playlist_tracks(playlist_url)
    if limit:
        tracks = tracks[:limit]
    _emit(f"Spotify returned {len(tracks)} tracks")

    needs_audio = download or analyze
    yt: YouTubeSource | None = None
    if needs_audio:
        settings = get_settings()
        cache_dir = settings.data_dir / "audio"
        yt = YouTubeSource(
            cache_dir=cache_dir,
            cookies_file=settings.yt_dlp_cookies_file,
        )

    track_rows: list[dict] = []
    total = len(tracks)
    _progress(0, total, "Démarrage…")
    for idx, t in enumerate(tracks, start=1):
        track_lbl = f"{t.artist} — {t.title}"[:80]
        _progress(idx - 1, total, f"[{idx}/{total}] préparation: {track_lbl}")
        row: dict[str, Any] = t.as_dict()
        audio_path: Path | None = None
        if yt is not None:
            try:
                _emit(f"  → download YouTube: {track_lbl}")
                _progress(idx - 1, total, f"[{idx}/{total}] YouTube DL: {track_lbl}")
                audio_path = yt.download(
                    spotify_id=t.spotify_id,
                    title=t.title,
                    artist=t.artist,
                    duration_ms=t.duration_ms,
                )
                row["audio_path"] = str(audio_path)
            except AudioSourceError as exc:
                log.warning(
                    "Échec download %s — %s : %s", t.artist, t.title, exc,
                )
                row["audio_path"] = None
                row["download_error"] = str(exc)
                _emit(f"  ! download failed: {t.artist} — {t.title}: {exc}")

        if analyze and audio_path is not None:
            def _on_step(step_key: str, step_label: str, fraction: float) -> None:
                current = (idx - 1) + fraction
                _progress(current, total, f"[{idx}/{total}] {step_label}: {track_lbl}")

            try:
                row["features"] = analyze_track(
                    audio_path, on_step=_on_step, on_log=_emit,
                )
                _emit(f"  ✓ analyse OK : {track_lbl}")
            except Exception as exc:  # noqa: BLE001
                log.exception("Échec analyse %s", audio_path)
                row["analysis_error"] = str(exc)
                _emit(f"  ! analysis failed: {audio_path.name}: {exc}")

        _progress(idx, total, f"[{idx}/{total}] OK : {track_lbl}")
        track_rows.append(row)

    skipped: list[dict[str, str]] = []
    if analyze:
        for row in track_rows:
            if "features" in row:
                continue
            reason = (
                row.get("download_error")
                or row.get("analysis_error")
                or "audio non disponible"
            )
            skipped.append({
                "spotify_id": row.get("spotify_id", ""),
                "artist": row.get("artist", ""),
                "title": row.get("title", ""),
                "reason": str(reason),
            })

        n_analyzed = total - len(skipped)
        _emit("")
        _emit("─── Rapport ───")
        _emit(f"{total} tracks Spotify")
        _emit(f"{n_analyzed} analysées avec succès")
        if skipped:
            _emit(f"{len(skipped)} retirées du process :")
            for s in skipped:
                _emit(f"  - {s['artist']} — {s['title']} : {s['reason']}")
        else:
            _emit("0 retirée du process")

    pattern: dict | None = None
    if analyze:
        _progress(total, total, "Extracting pattern…")
        _emit("Extracting playlist pattern from track features")
        track_features = [r["features"] for r in track_rows if "features" in r]
        if track_features:
            pattern = extract_pattern(track_features)

    playlist_meta: PlaylistMeta | None = None
    if save:
        _emit("Persisting playlist + analyses + pattern to SQLite")
        playlist_meta = client.get_playlist_meta(playlist_url)
        _persist(log, playlist_meta, tracks, track_rows, pattern)

    report_path: Path | None = None
    if pattern is not None:
        tracks_data = [
            {"artist": t.artist, "title": t.title, "features": r.get("features")}
            for t, r in zip(tracks, track_rows, strict=False)
            if "features" in r
        ]
        playlist_name = (
            playlist_meta.name if playlist_meta else "Playlist"
        )
        brief_md = generate_brief(
            pattern, playlist_name=playlist_name, tracks_data=tracks_data,
        )
        playlist_id = SpotifyClient.parse_playlist_id(playlist_url)
        report_dir = get_settings().data_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{playlist_id}.md"
        report_path.write_text(brief_md, encoding="utf-8")
        _emit(f"Brief written: {report_path}")

    result: dict[str, Any] = {"tracks": track_rows, "skipped": skipped}
    if playlist_meta is not None:
        result["playlist"] = playlist_meta.as_dict()
        result["playlist_spotify_id"] = playlist_meta.spotify_id
    elif tracks:
        try:
            result["playlist_spotify_id"] = SpotifyClient.parse_playlist_id(
                playlist_url,
            )
        except Exception:  # noqa: BLE001
            pass
    if pattern is not None:
        result["pattern"] = pattern
    if report_path is not None:
        result["report_path"] = str(report_path)
    return result


def main() -> int:
    load_dotenv()
    _setup_logging()
    log = logging.getLogger("backend.cli.pipeline")

    parser = argparse.ArgumentParser(
        description="Sanity check Spotify Pattern Analyzer.",
    )
    parser.add_argument(
        "playlist_url",
        help="URL, URI ou ID Spotify d'une playlist",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limiter à N tracks")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Télécharger l'audio via YouTube (sans analyse).",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Tempo + tonalité + énergie + spectral + structure + timbre. "
             "Auto-télécharge si l'audio manque.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Persiste playlist + tracks + analyses + pattern en SQLite. "
             "Requiert --analyze.",
    )
    args = parser.parse_args()

    if args.save and not args.analyze:
        parser.error("--save requires --analyze")

    try:
        result = run_pipeline(
            args.playlist_url,
            save=args.save,
            limit=args.limit,
            download=args.download,
            analyze=args.analyze,
        )
    except (EditorialPlaylistError, PlaylistAccessError) as exc:
        log.error("%s", exc)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
