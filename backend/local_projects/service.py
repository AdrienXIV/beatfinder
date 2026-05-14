"""Service projets locaux : création, upload tracks, suppression, pipeline d'analyse.

Convention : un project local est stocké comme un `Playlist` avec
`spotify_id = "local:{uuid_hex}"`. Les tracks ont `spotify_id = "local:{proj_uuid}:{file_hash}"`.
Pas de modif schema DB, juste convention de naming.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Literal

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
from backend.report_generator import generate_brief
from backend.services.pattern_extractor import extract_pattern
from backend.types import LogCallback, ProgressCallback

from ._audio_io import (
    ALLOWED_EXTENSIONS,
    LOCAL_PLAYLIST_PREFIX,
    _find_audio_path,
    _read_metadata,
    _safe_filename,
)

AnalyzeMode = Literal["new", "full"]

log = logging.getLogger("backend.local_projects")


def is_local_playlist(spotify_id: str) -> bool:
    return spotify_id.startswith(LOCAL_PLAYLIST_PREFIX)


def make_local_id() -> str:
    return f"{LOCAL_PLAYLIST_PREFIX}{uuid.uuid4().hex}"


def brief_filename(spotify_id: str) -> str:
    """Convertit un spotify_id (potentiellement local:xxx) en nom de fichier safe."""
    return spotify_id.replace(":", "_")


def create_project(
    name: str, owner_display_name: str | None = None,
) -> dict[str, Any]:
    """Crée un nouveau project local vide."""
    engine = init_db()
    Session = make_session_factory(engine)
    with Session() as session:
        spotify_id = make_local_id()
        playlist = Playlist(
            spotify_id=spotify_id,
            name=name,
            owner_display_name=owner_display_name or "Local",
            description=None,
        )
        session.add(playlist)
        session.commit()
        session.refresh(playlist)
        return {
            "spotify_id": playlist.spotify_id,
            "name": playlist.name,
            "owner_display_name": playlist.owner_display_name,
            "created_at": playlist.created_at,
        }


def add_tracks(
    project_spotify_id: str,
    files: list[tuple[str, bytes]],
    overrides: dict[str, dict[str, str]] | None = None,
    data_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Ajoute N tracks à un project local. files = liste (filename, bytes)."""
    if data_dir is None:
        data_dir = get_settings().data_dir
    overrides = overrides or {}

    engine = init_db()
    Session = make_session_factory(engine)
    with Session() as session:
        playlist = session.scalar(
            select(Playlist).where(Playlist.spotify_id == project_spotify_id),
        )
        if playlist is None:
            raise ValueError(f"Project {project_spotify_id!r} not found")
        if not is_local_playlist(playlist.spotify_id):
            raise ValueError(f"Playlist {project_spotify_id!r} is not local")

        proj_uuid = playlist.spotify_id[len(LOCAL_PLAYLIST_PREFIX):]
        audio_dir = data_dir / "audio" / "local" / proj_uuid
        audio_dir.mkdir(parents=True, exist_ok=True)

        existing_count = len(playlist.tracks)
        added: list[dict[str, Any]] = []

        for idx, (raw_name, content) in enumerate(files):
            safe = _safe_filename(raw_name)
            ext = Path(safe).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                log.warning("Skipped %s : extension %s not allowed", raw_name, ext)
                continue

            file_hash = hashlib.md5(content).hexdigest()[:16]
            stored_name = f"{file_hash}_{safe}"
            audio_path = audio_dir / stored_name

            if not audio_path.exists():
                audio_path.write_bytes(content)

            meta = _read_metadata(audio_path)
            override = overrides.get(raw_name, {})
            title = (override.get("title") or meta["title"]).strip()
            artist = (override.get("artist") or meta["artist"]).strip()

            track_spotify_id = (
                f"{LOCAL_PLAYLIST_PREFIX}{proj_uuid}:{file_hash}"
            )
            track = session.scalar(
                select(Track).where(Track.spotify_id == track_spotify_id),
            )
            if track is None:
                track = Track(
                    spotify_id=track_spotify_id,
                    title=title or audio_path.stem,
                    artist=artist,
                    duration_ms=meta["duration_ms"],
                    release_date=None,
                )
                session.add(track)
                session.flush()
            else:
                track.title = title or track.title
                if artist:
                    track.artist = artist
                if meta["duration_ms"]:
                    track.duration_ms = meta["duration_ms"]

            pt = session.scalar(
                select(PlaylistTrack).where(
                    PlaylistTrack.playlist_id == playlist.id,
                    PlaylistTrack.track_id == track.id,
                ),
            )
            if pt is None:
                session.add(PlaylistTrack(
                    playlist_id=playlist.id,
                    track_id=track.id,
                    position=existing_count + idx,
                ))

            added.append({
                "spotify_id": track.spotify_id,
                "title": title or audio_path.stem,
                "artist": artist,
                "duration_ms": meta["duration_ms"],
                "audio_path": str(audio_path),
                "filename": raw_name,
            })

        session.commit()
        return added


def delete_project(
    project_spotify_id: str, data_dir: Path | None = None,
) -> dict[str, Any]:
    """Supprime un project local + ses tracks + analyses + pattern + fichiers audio.

    Pour les Track locales (spotify_id préfixé `local:{proj_uuid}:`) on cascade.
    Le dossier audio + les briefs/CSV sont aussi supprimés.
    """
    if data_dir is None:
        data_dir = get_settings().data_dir

    engine = init_db()
    Session = make_session_factory(engine)
    deleted = {
        "spotify_id": project_spotify_id,
        "n_tracks": 0,
        "n_audio_files": 0,
        "n_briefs": 0,
    }

    with Session() as session:
        playlist = session.scalar(
            select(Playlist).where(Playlist.spotify_id == project_spotify_id),
        )
        if playlist is None:
            raise ValueError(f"Project {project_spotify_id!r} not found")
        if not is_local_playlist(playlist.spotify_id):
            raise ValueError(f"Playlist {project_spotify_id!r} is not local")

        proj_uuid = playlist.spotify_id[len(LOCAL_PLAYLIST_PREFIX):]
        track_prefix = f"{LOCAL_PLAYLIST_PREFIX}{proj_uuid}:"

        # Recup les Track locales liées à ce projet AVANT de delete la Playlist
        # (sinon on perd l'accès via playlist.tracks)
        local_tracks = [
            pt.track
            for pt in playlist.tracks
            if pt.track.spotify_id.startswith(track_prefix)
        ]
        deleted["n_tracks"] = len(local_tracks)

        # Delete la Playlist : cascade ORM supprime PlaylistTrack + PlaylistPattern
        session.delete(playlist)
        session.flush()

        # Delete les Track locales (cascade ORM supprime leurs TrackAnalysis)
        for track in local_tracks:
            session.delete(track)

        session.commit()

    # File system cleanup
    audio_dir = data_dir / "audio" / "local" / proj_uuid
    if audio_dir.is_dir():
        deleted["n_audio_files"] = sum(1 for _ in audio_dir.glob("*") if _.is_file())
        shutil.rmtree(audio_dir, ignore_errors=True)

    fname = brief_filename(project_spotify_id)
    path = data_dir / "reports" / f"{fname}.md"
    if path.is_file():
        path.unlink()
        deleted["n_briefs"] += 1

    return deleted


def run_local_pipeline(
    project_spotify_id: str,
    *,
    mode: AnalyzeMode = "new",
    on_progress: ProgressCallback | None = None,
    on_log: LogCallback | None = None,
) -> dict[str, Any]:
    """Analyse les tracks d'un project local. Skip Spotify+YouTube, just librosa.

    mode=="new" : skip les tracks déjà analysées (TrackAnalysis existante + audio
    file présent), charge leurs features depuis la DB pour le pattern global.
    mode=="full" : re-analyse toutes les tracks (utile si tu as modifié un fichier
    audio existant).
    """
    runner_log = logging.getLogger("backend.local_projects.run")

    def _progress(c: int, t: int, label: str = "") -> None:
        if on_progress:
            try:
                on_progress(c, t, label)
            except Exception:  # noqa: BLE001
                runner_log.warning("on_progress raised", exc_info=True)

    def _emit(line: str) -> None:
        runner_log.info(line)
        if on_log:
            try:
                on_log(line)
            except Exception:  # noqa: BLE001
                runner_log.warning("on_log raised", exc_info=True)

    data_dir = get_settings().data_dir
    engine = init_db()
    Session = make_session_factory(engine)

    with Session() as session:
        playlist = session.scalar(
            select(Playlist).where(Playlist.spotify_id == project_spotify_id),
        )
        if playlist is None:
            raise ValueError(f"Project {project_spotify_id!r} not found")
        if not is_local_playlist(playlist.spotify_id):
            raise ValueError(f"Playlist {project_spotify_id!r} is not local")

        pt_rows = sorted(playlist.tracks, key=lambda x: x.position)
        if not pt_rows:
            _emit("No tracks in project, nothing to analyze")
            return {
                "playlist_spotify_id": project_spotify_id,
                "tracks": [],
            }

        _emit(
            f"Analyzing {len(pt_rows)} local tracks (mode={mode})",
        )
        total = len(pt_rows)
        track_rows: list[dict[str, Any]] = []
        n_reused = 0
        n_analyzed = 0
        _progress(0, total, "Démarrage…")

        def _display(t: Track) -> str:
            name = f"{t.artist} — {t.title}" if t.artist else t.title
            return name[:80]

        for idx, pt in enumerate(pt_rows, start=1):
            t = pt.track
            label = _display(t)

            audio_path: Path | None = None
            latest = session.scalar(
                select(TrackAnalysis)
                .where(TrackAnalysis.track_id == t.id)
                .order_by(TrackAnalysis.id.desc()),
            )
            if latest and latest.audio_path:
                candidate = Path(latest.audio_path)
                if candidate.is_file():
                    audio_path = candidate
            if audio_path is None:
                audio_path = _find_audio_path(
                    t.spotify_id, project_spotify_id, data_dir,
                )

            # En mode "new" : si une analyse existe ET le fichier audio est
            # toujours présent, on réutilise les features sans relancer librosa.
            if (
                mode == "new"
                and latest is not None
                and audio_path is not None
                and audio_path.is_file()
            ):
                _emit(f"  ✓ [cache] {label}")
                _progress(idx, total, f"[{idx}/{total}] cached: {label}")
                track_rows.append({
                    "spotify_id": t.spotify_id,
                    "artist": t.artist,
                    "title": t.title,
                    "audio_path": str(audio_path),
                    "features": latest.features_json,
                    "from_cache": True,
                })
                n_reused += 1
                continue

            # Avant l'analyse : on annonce ce qu'on traite, mais le compteur
            # ne reflète que les tracks DÉJÀ terminées (idx-1) pour ne pas
            # mentir au % de progression.
            _emit(f"  → analyse {label}")
            _progress(idx - 1, total, f"[{idx}/{total}] préparation: {label}")

            if audio_path is None or not audio_path.is_file():
                _emit(f"  ! audio missing for {label}")
                track_rows.append({
                    "spotify_id": t.spotify_id,
                    "artist": t.artist,
                    "title": t.title,
                    "missing_audio": True,
                })
                _progress(idx, total, f"[{idx}/{total}] audio manquant: {label}")
                continue

            def _on_step(step_key: str, step_label: str, fraction: float) -> None:
                # fraction ∈ [0,1] = avancement intra-track → on incrémente le
                # `current` global pour que la barre de progression soit fluide.
                current = (idx - 1) + fraction
                _progress(current, total, f"[{idx}/{total}] {step_label}: {label}")

            try:
                features = analyze_track(
                    audio_path, on_step=_on_step, on_log=_emit,
                )
            except Exception as exc:  # noqa: BLE001
                runner_log.exception("Analyse failed for %s", audio_path)
                _emit(f"  ! analyze failed for {audio_path.name}: {exc}")
                track_rows.append({
                    "spotify_id": t.spotify_id,
                    "artist": t.artist,
                    "title": t.title,
                    "analysis_error": str(exc),
                })
                _progress(idx, total, f"[{idx}/{total}] erreur: {label}")
                continue

            session.add(TrackAnalysis(
                track_id=t.id,
                features_json=features,
                audio_path=str(audio_path),
            ))
            n_analyzed += 1
            _emit(f"  ✓ analyse OK : {label}")
            _progress(idx, total, f"[{idx}/{total}] OK : {label}")
            track_rows.append({
                "spotify_id": t.spotify_id,
                "artist": t.artist,
                "title": t.title,
                "audio_path": str(audio_path),
                "features": features,
            })

        _emit(
            f"Tracks: {n_analyzed} freshly analyzed, {n_reused} reused from cache",
        )

        _progress(total, total, "Extracting pattern…")
        _emit("Extracting playlist pattern")
        track_features = [r["features"] for r in track_rows if "features" in r]
        pattern: dict[str, Any] | None = None
        if track_features:
            pattern = extract_pattern(track_features)
            session.add(PlaylistPattern(
                playlist_id=playlist.id,
                pattern_json=pattern,
                n_tracks_analyzed=int(pattern.get("n_tracks", 0)),
            ))

        report_path: Path | None = None
        if pattern is not None:
            tracks_data = [
                {"artist": r["artist"], "title": r["title"], "features": r["features"]}
                for r in track_rows
                if "features" in r
            ]
            brief_md = generate_brief(
                pattern, playlist_name=playlist.name, tracks_data=tracks_data,
            )
            report_dir = data_dir / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            fname = brief_filename(playlist.spotify_id)
            report_path = report_dir / f"{fname}.md"
            report_path.write_text(brief_md, encoding="utf-8")
            _emit(f"Brief written: {report_path}")

        session.commit()
        return {
            "playlist_spotify_id": project_spotify_id,
            "mode": mode,
            "tracks": track_rows,
            "n_analyzed": n_analyzed,
            "n_reused": n_reused,
            "pattern": pattern,
            "report_path": str(report_path) if report_path else None,
        }
