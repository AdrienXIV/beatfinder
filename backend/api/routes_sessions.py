"""Routes FastAPI sessions créatives.

Une "session créative" est un workflow guidé pour démarrer une track from
scratch en suivant une cible d'inspiration figée. Chaque version uploadée
(v1, v2, …) est analysée indépendamment — pas de moyennage.

  POST   /sessions                      crée une session (Phase 1 : source = URL Spotify)
  GET    /sessions                      liste les sessions actives
  GET    /sessions/{spotify_id}         détail (plan A→Z + versions)
  POST   /sessions/{spotify_id}/versions    upload audio + analyse + fit_score
  DELETE /sessions/{spotify_id}         hard delete (versions + audio + track orpheline)
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.api.deps import get_data_dir, get_job_queue, get_session
from backend.api.job_runner import run_session_upload_job
from backend.api.jobs import JobQueue
from backend.api.schemas import (
    CreateSessionIn,
    CreativeSessionDetailOut,
    CreativeSessionSummaryOut,
    JobOut,
    SessionVersionOut,
    TrackOut,
)
from backend.domain.models import (
    CreativeSession,
    Playlist,
    PlaylistPattern,
    PlaylistTrack,
    Track,
    TrackAnalysis,
    TrackOverride,
)
from backend.infrastructure.spotify_client import SpotifyClient
from backend.services.session_brief import generate_session_brief
from backend.services.track_overrides import (
    apply_overrides,
    bpm_alt_hypotheses,
    compute_confidence,
    regenerate_pattern_for_playlist,
)

log = logging.getLogger("backend.api.routes_sessions")

router = APIRouter(prefix="/sessions", tags=["sessions"])

SessionDep = Annotated[Session, Depends(get_session)]
DataDirDep = Annotated[Path, Depends(get_data_dir)]
QueueDep = Annotated[JobQueue, Depends(get_job_queue)]

ALLOWED_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aiff"})

# Spotify expose plusieurs types de ressources mais Beatfinder n'analyse que
# tracks et playlists. On bloque les autres avec un 400 explicite plutôt que
# de laisser tomber sur le 404 générique "introuvable en DB".
UNSUPPORTED_SPOTIFY_TYPE_RE = re.compile(
    r"(?:spotify:|open\.spotify\.com/)(album|artist|show|episode)[:/]",
    re.IGNORECASE,
)
UNSUPPORTED_TYPE_HINTS = {
    "album": (
        "Ouvre l'album sur Spotify et copie le lien d'une track précise, "
        "ou crée une playlist contenant ces tracks."
    ),
    "artist": (
        "Utilise une track ou une playlist spécifique de l'artiste, "
        "pas le profil entier."
    ),
    "show": "Les podcasts ne sont pas analysables musicalement.",
    "episode": "Les podcasts ne sont pas analysables musicalement.",
}


def _to_summary(s: CreativeSession) -> CreativeSessionSummaryOut:
    last_fit = None
    if s.versions:
        last = s.versions[-1]  # ordre version_number ASC
        last_fit = last.fit_score
    return CreativeSessionSummaryOut(
        spotify_id=s.spotify_id,
        name=s.name,
        target_kind=s.target_kind,  # type: ignore[arg-type]
        target_name=s.target_name,
        n_versions=len(s.versions),
        last_fit_score=last_fit,
        is_locked=s.is_locked,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _build_target_tracks(db: Session, target_ref: str) -> list[TrackOut] | None:
    """Construit la liste des tracks d'une playlist cible (pour mode draft).

    Mêmes infos que `routes_playlists._track_to_out` mais bulk pour 1 playlist
    cible. Renvoie None si target_ref ne correspond à aucune playlist.
    """
    playlist = db.scalar(
        select(Playlist)
        .where(Playlist.spotify_id == target_ref)
        .options(selectinload(Playlist.tracks).selectinload(PlaylistTrack.track)),
    )
    if playlist is None:
        return None

    pt_rows = sorted(playlist.tracks, key=lambda x: x.position)
    track_ids = [pt.track_id for pt in pt_rows]
    if not track_ids:
        return []

    # Charger dernières analyses + overrides en bulk
    from sqlalchemy import func as sa_func

    last_ids_subq = (
        select(sa_func.max(TrackAnalysis.id))
        .where(TrackAnalysis.track_id.in_(track_ids))
        .group_by(TrackAnalysis.track_id)
        .scalar_subquery()
    )
    latest_rows = db.scalars(
        select(TrackAnalysis).where(TrackAnalysis.id.in_(last_ids_subq)),
    ).all()
    latest_by_track = {a.track_id: a for a in latest_rows}

    overrides = db.scalars(
        select(TrackOverride).where(TrackOverride.track_id.in_(track_ids)),
    ).all()
    overrides_by_track = {ov.track_id: ov for ov in overrides}

    out: list[TrackOut] = []
    for pt in pt_rows:
        analysis = latest_by_track.get(pt.track_id)
        raw_features: dict = (analysis.features_json or {}) if analysis else {}
        override = overrides_by_track.get(pt.track_id)
        features = apply_overrides(raw_features, override)
        tempo = features.get("tempo") or {}
        tonality = features.get("tonality") or {}
        confidence_low, confidence_reasons = compute_confidence(raw_features)
        out.append(
            TrackOut(
                spotify_id=pt.track.spotify_id,
                title=pt.track.title,
                artist=pt.track.artist,
                duration_ms=pt.track.duration_ms,
                release_date=pt.track.release_date,
                position=pt.position,
                has_analysis=analysis is not None,
                audio_path=analysis.audio_path if analysis else None,
                bpm=tempo.get("bpm"),
                key_note=tonality.get("note"),
                key_mode=tonality.get("mode"),
                key_uncertain=tonality.get("is_uncertain"),
                is_overridden=override is not None,
                confidence_low=confidence_low,
                confidence_reasons=confidence_reasons,
                bpm_alt_hypotheses=bpm_alt_hypotheses(tempo.get("bpm")),
            ),
        )
    return out


def _build_target_track(db: Session, target_ref: str) -> TrackOut | None:
    """Construit le TrackOut de la track cible (avec overrides + confidence).

    Utilisé par les pages session/[id] où la cible est une track isolée :
    permet d'afficher BPM/Key courants + bouton de correction.
    """
    track = db.scalar(select(Track).where(Track.spotify_id == target_ref))
    if track is None:
        return None
    analysis = db.scalar(
        select(TrackAnalysis)
        .where(TrackAnalysis.track_id == track.id)
        .order_by(TrackAnalysis.id.desc()),
    )
    raw_features: dict = (analysis.features_json or {}) if analysis else {}
    override = db.scalar(
        select(TrackOverride).where(TrackOverride.track_id == track.id),
    )
    features = apply_overrides(raw_features, override)
    tempo = features.get("tempo") or {}
    tonality = features.get("tonality") or {}
    confidence_low, confidence_reasons = compute_confidence(raw_features)
    return TrackOut(
        spotify_id=track.spotify_id,
        title=track.title,
        artist=track.artist,
        duration_ms=track.duration_ms,
        release_date=track.release_date,
        position=0,
        has_analysis=analysis is not None,
        audio_path=analysis.audio_path if analysis else None,
        bpm=tempo.get("bpm"),
        key_note=tonality.get("note"),
        key_mode=tonality.get("mode"),
        key_uncertain=tonality.get("is_uncertain"),
        is_overridden=override is not None,
        confidence_low=confidence_low,
        confidence_reasons=confidence_reasons,
        bpm_alt_hypotheses=bpm_alt_hypotheses(tempo.get("bpm")),
    )


def _to_detail(s: CreativeSession, db: Session) -> CreativeSessionDetailOut:
    target_track = None
    target_tracks = None
    if s.target_kind == "spotify_track":
        target_track = _build_target_track(db, s.target_ref)
    elif s.target_kind in ("spotify_playlist", "local_playlist"):
        target_tracks = _build_target_tracks(db, s.target_ref)
    return CreativeSessionDetailOut(
        spotify_id=s.spotify_id,
        name=s.name,
        target_kind=s.target_kind,  # type: ignore[arg-type]
        target_ref=s.target_ref,
        target_name=s.target_name,
        target_pattern=s.target_pattern_json,
        target_track=target_track,
        target_tracks=target_tracks,
        ambiance=s.ambiance_json,
        plan_md=s.plan_md,
        versions=[SessionVersionOut.model_validate(v) for v in s.versions],
        is_locked=s.is_locked,
        locked_at=s.locked_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _resolve_source(
    session: Session, source_url: str, data_dir: Path | None = None,
) -> tuple[str, str, str, dict]:
    """Résout une URL/ID Spotify en (target_kind, target_ref, target_name, pattern).

    Tente successivement : URL playlist → URL track → ID brut.
    Lève 400 si type Spotify non supporté (album/artist/show/episode),
    404 si pas trouvé en DB, 409 si trouvé mais pas encore analysé.

    **Régénère le pattern** de la cible avant snapshot — garantit que la
    session est créée sur la version la plus fraîche (avec overrides appliqués).
    Une fois snapshot dans `target_pattern_json`, la cible est figée et ne
    bouge plus, même si la playlist est ré-analysée ou si ses overrides
    changent après coup.
    """
    # 0. Rejet explicite des types Spotify non supportés (album/artist/...)
    unsupported_match = UNSUPPORTED_SPOTIFY_TYPE_RE.search(source_url)
    if unsupported_match:
        kind = unsupported_match.group(1).lower()
        hint = UNSUPPORTED_TYPE_HINTS.get(kind, "")
        raise HTTPException(
            status_code=400,
            detail=(
                f"Type Spotify {kind!r} non supporté. Beatfinder n'analyse que "
                f"les tracks et playlists. {hint}".strip()
            ),
        )

    # 1. Essai URL playlist
    try:
        playlist_id = SpotifyClient.parse_playlist_id(source_url)
    except (ValueError, AttributeError):
        playlist_id = None

    if playlist_id:
        playlist = session.scalar(
            select(Playlist).where(Playlist.spotify_id == playlist_id),
        )
        if playlist is not None:
            existing = session.scalar(
                select(PlaylistPattern)
                .where(PlaylistPattern.playlist_id == playlist.id)
                .order_by(PlaylistPattern.id.desc()),
            )
            if existing is None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Playlist {playlist_id!r} trouvée mais pas encore "
                        "analysée. Lance d'abord son analyse depuis "
                        "'Analyser Spotify'."
                    ),
                )
            # Régénère le pattern pour intégrer les éventuels overrides AVANT
            # de figer le snapshot dans la session. Si aucune track n'a
            # d'override, le pattern recalculé est identique au précédent.
            fresh = regenerate_pattern_for_playlist(session, playlist, data_dir)
            session.commit()
            pattern_json = fresh if fresh is not None else existing.pattern_json
            return (
                "spotify_playlist",
                playlist.spotify_id,
                playlist.name,
                pattern_json,
            )

    # 2. Essai URL track
    try:
        track_id = SpotifyClient.parse_track_id(source_url)
    except (ValueError, AttributeError):
        track_id = source_url.strip()  # fallback: ID brut peut-être ?

    track = session.scalar(
        select(Track).where(Track.spotify_id == track_id),
    )
    if track is not None:
        analysis = session.scalar(
            select(TrackAnalysis)
            .where(TrackAnalysis.track_id == track.id)
            .order_by(TrackAnalysis.id.desc()),
        )
        if analysis is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Track {track_id!r} trouvée en DB mais pas encore "
                    "analysée. Lance d'abord son analyse depuis "
                    "'Analyser Spotify'."
                ),
            )
        # Wrap features d'une track unique en pseudo-pattern compatible
        # `generate_session_brief`. Override appliqué AVANT extraction pour
        # que la session reflète la correction manuelle.
        from backend.services.pattern_extractor import extract_pattern
        override = session.scalar(
            select(TrackOverride).where(TrackOverride.track_id == track.id),
        )
        features = apply_overrides(analysis.features_json, override)
        pattern_json = extract_pattern([features])
        target_name = f"{track.artist} — {track.title}"
        return ("spotify_track", track.spotify_id, target_name, pattern_json)

    raise HTTPException(
        status_code=404,
        detail=(
            f"Source {source_url!r} introuvable en DB. Analyse-la d'abord "
            "depuis 'Analyser Spotify' (URL playlist ou track) avant de "
            "créer une session."
        ),
    )


@router.post("", response_model=CreativeSessionDetailOut)
def create_session(
    payload: CreateSessionIn,
    db: SessionDep,
    data_dir: DataDirDep,
) -> CreativeSessionDetailOut:
    """Crée une session : résout la cible, snapshot le pattern, génère le plan A→Z.

    La cible est **figée** dans `target_pattern_json` au moment de la création
    — pas de re-sync ultérieur. Le pattern est régénéré avant le snapshot pour
    intégrer les overrides éventuels.
    """
    target_kind, target_ref, target_name, target_pattern = _resolve_source(
        db, payload.source_url, data_dir,
    )

    plan_md = generate_session_brief(
        target_pattern,
        target_name=target_name,
        ambiance=payload.ambiance,
    )

    spotify_id = f"session_{uuid.uuid4().hex[:12]}"
    name = target_name
    sess = CreativeSession(
        spotify_id=spotify_id,
        name=name,
        target_kind=target_kind,
        target_ref=target_ref,
        target_name=target_name,
        target_pattern_json=target_pattern,
        ambiance_json=payload.ambiance,
        plan_md=plan_md,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return _to_detail(sess, db)


@router.get("", response_model=list[CreativeSessionSummaryOut])
def list_sessions(db: SessionDep) -> list[CreativeSessionSummaryOut]:
    """Liste les sessions actives (non archivées), tri ordre récent."""
    sessions = db.scalars(
        select(CreativeSession)
        .where(CreativeSession.archived == False)  # noqa: E712
        .options(selectinload(CreativeSession.versions))
        .order_by(CreativeSession.updated_at.desc()),
    ).all()
    return [_to_summary(s) for s in sessions]


@router.get("/{spotify_id}", response_model=CreativeSessionDetailOut)
def get_session_detail(
    spotify_id: str, db: SessionDep,
) -> CreativeSessionDetailOut:
    sess = db.scalar(
        select(CreativeSession)
        .where(CreativeSession.spotify_id == spotify_id)
        .options(selectinload(CreativeSession.versions)),
    )
    if sess is None:
        raise HTTPException(
            status_code=404, detail=f"Session {spotify_id!r} introuvable",
        )
    return _to_detail(sess, db)


@router.post(
    "/{spotify_id}/versions", response_model=JobOut, status_code=202,
)
async def upload_version(
    spotify_id: str,
    db: SessionDep,
    data_dir: DataDirDep,
    queue: QueueDep,
    file: UploadFile = File(...),
) -> JobOut:
    """Upload une version audio + crée un job d'analyse asynchrone.

    Le fichier est sauvé sur disque puis l'analyse (longue : 10-30s) tourne
    dans un thread. La route retourne immédiatement un JobOut 202 ; le client
    suit la progression via `GET /jobs/{id}/stream` (SSE) puis re-fetch la
    session quand `status=done`.

    Chaque version a son propre features_json — pas de moyennage avec les
    précédentes. Le fit_score mesure la convergence vers la cible figée.
    """
    sess = db.scalar(
        select(CreativeSession)
        .where(CreativeSession.spotify_id == spotify_id)
        .options(selectinload(CreativeSession.versions)),
    )
    if sess is None:
        raise HTTPException(
            status_code=404, detail=f"Session {spotify_id!r} introuvable",
        )
    if not sess.is_locked:
        raise HTTPException(
            status_code=409,
            detail=(
                "La session est encore en brouillon. Verrouille la cible "
                "avant d'uploader une version."
            ),
        )

    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Extension {ext!r} non supportée. "
                f"Accepté : {sorted(ALLOWED_AUDIO_EXTENSIONS)}"
            ),
        )

    next_n = (max((v.version_number for v in sess.versions), default=0)) + 1
    audio_dir = data_dir / "audio" / "sessions" / sess.spotify_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"v{next_n}{ext}"
    content = await file.read()
    audio_path.write_bytes(content)

    job = queue.create("session-version-upload")
    task = asyncio.create_task(
        run_session_upload_job(queue, job.id, spotify_id, audio_path, next_n),
        name=f"session-upload:{job.id}",
    )
    queue.attach_task(job.id, task)
    return JobOut(**job.to_dict())


def _regenerate_target_pattern(
    db: Session, sess: CreativeSession, data_dir: Path,
) -> tuple[dict, str]:
    """Recalcule target_pattern_json + plan_md depuis l'état actuel de la cible.

    Utilisé au lock : on fige la cible avec les overrides courants. Si la
    cible est une playlist, on lance `regenerate_pattern_for_playlist` pour
    avoir un pattern frais. Si c'est une track isolée, on wrap son features
    + override courant.

    Lève 409 si la cible n'a plus de données (track supprimée, etc.).
    """
    if sess.target_kind in ("spotify_playlist", "local_playlist"):
        playlist = db.scalar(
            select(Playlist).where(Playlist.spotify_id == sess.target_ref),
        )
        if playlist is None:
            raise HTTPException(
                status_code=409,
                detail=f"Playlist {sess.target_ref!r} introuvable",
            )
        pattern = regenerate_pattern_for_playlist(db, playlist, data_dir)
        db.commit()
        if pattern is None:
            raise HTTPException(
                status_code=409,
                detail="Playlist cible n'a aucune track analysée",
            )
    elif sess.target_kind == "spotify_track":
        track = db.scalar(
            select(Track).where(Track.spotify_id == sess.target_ref),
        )
        if track is None:
            raise HTTPException(
                status_code=409,
                detail=f"Track {sess.target_ref!r} introuvable",
            )
        analysis = db.scalar(
            select(TrackAnalysis)
            .where(TrackAnalysis.track_id == track.id)
            .order_by(TrackAnalysis.id.desc()),
        )
        if analysis is None:
            raise HTTPException(
                status_code=409,
                detail=f"Track {sess.target_ref!r} pas analysée",
            )
        from backend.services.pattern_extractor import extract_pattern
        override = db.scalar(
            select(TrackOverride).where(TrackOverride.track_id == track.id),
        )
        features = apply_overrides(analysis.features_json, override)
        pattern = extract_pattern([features])
    else:
        raise HTTPException(
            status_code=400,
            detail=f"target_kind {sess.target_kind!r} non supporté",
        )

    plan_md = generate_session_brief(
        pattern,
        target_name=sess.target_name,
        ambiance=sess.ambiance_json,
    )
    return pattern, plan_md


@router.post("/{spotify_id}/lock", response_model=CreativeSessionDetailOut)
def lock_session(
    spotify_id: str, db: SessionDep, data_dir: DataDirDep,
) -> CreativeSessionDetailOut:
    """Verrouille la session : fige target_pattern + plan_md.

    À ce moment, l'utilisateur a corrigé les BPM/Key des tracks de la cible.
    On régénère le pattern (qui inclut les overrides) puis le plan A→Z.
    Après lock, les uploads de versions sont possibles.
    """
    sess = db.scalar(
        select(CreativeSession)
        .where(CreativeSession.spotify_id == spotify_id)
        .options(selectinload(CreativeSession.versions)),
    )
    if sess is None:
        raise HTTPException(
            status_code=404, detail=f"Session {spotify_id!r} introuvable",
        )
    if sess.is_locked:
        return _to_detail(sess, db)

    pattern, plan_md = _regenerate_target_pattern(db, sess, data_dir)
    sess.target_pattern_json = pattern
    sess.plan_md = plan_md
    sess.is_locked = True
    sess.locked_at = datetime.now(UTC)
    db.commit()
    db.refresh(sess)
    return _to_detail(sess, db)


@router.post("/{spotify_id}/unlock", response_model=CreativeSessionDetailOut)
def unlock_session(
    spotify_id: str, db: SessionDep,
) -> CreativeSessionDetailOut:
    """Déverrouille la session, retour en mode brouillon.

    Les versions uploadées restent en DB mais leur fit_score devient
    désynchronisé si l'utilisateur modifie la cible. Au prochain lock, le
    target_pattern_json sera regénéré.
    """
    sess = db.scalar(
        select(CreativeSession)
        .where(CreativeSession.spotify_id == spotify_id)
        .options(selectinload(CreativeSession.versions)),
    )
    if sess is None:
        raise HTTPException(
            status_code=404, detail=f"Session {spotify_id!r} introuvable",
        )
    sess.is_locked = False
    sess.locked_at = None
    db.commit()
    db.refresh(sess)
    return _to_detail(sess, db)


def _delete_orphan_track_if_unused(
    db: Session,
    target_ref: str,
    data_dir: Path,
    exclude_session_id: int,
) -> bool:
    """Supprime une track Spotify isolée si plus aucune référence active.

    Une track est "orpheline" si :
    - Aucune autre session active (`archived=False`) ne la cible
    - Aucune playlist ne la contient (via PlaylistTrack)

    Supprime alors : la Track (cascade auto sur TrackAnalysis via SQLAlchemy),
    le TrackOverride éventuel (FK sans cascade), et le fichier audio cache
    `data/audio/{spotify_id}.mp3`.

    Args:
        target_ref: `track.spotify_id` de la track à potentiellement supprimer.
        exclude_session_id: la session en cours de suppression (à ne pas
            compter dans les références actives).

    Returns: True si la track a été supprimée, False sinon.
    """
    track = db.scalar(select(Track).where(Track.spotify_id == target_ref))
    if track is None:
        return False

    other_sessions = (
        db.scalar(
            select(func.count())
            .select_from(CreativeSession)
            .where(
                CreativeSession.target_kind == "spotify_track",
                CreativeSession.target_ref == target_ref,
                CreativeSession.archived == False,  # noqa: E712
                CreativeSession.id != exclude_session_id,
            ),
        )
        or 0
    )
    playlists_ref = (
        db.scalar(
            select(func.count())
            .select_from(PlaylistTrack)
            .where(PlaylistTrack.track_id == track.id),
        )
        or 0
    )

    if other_sessions > 0 or playlists_ref > 0:
        return False

    # Plus aucune référence → on supprime
    override = db.scalar(
        select(TrackOverride).where(TrackOverride.track_id == track.id),
    )
    if override is not None:
        db.delete(override)

    audio_path = data_dir / "audio" / f"{track.spotify_id}.mp3"
    if audio_path.is_file():
        try:
            audio_path.unlink()
        except OSError as exc:
            log.warning("Could not delete audio %s: %s", audio_path, exc)

    db.delete(track)  # cascade auto sur TrackAnalysis
    return True


@router.delete("/{spotify_id}", status_code=204)
def delete_session(
    spotify_id: str, db: SessionDep, data_dir: DataDirDep,
) -> None:
    """Supprime définitivement une session (hard delete).

    - SessionVersion supprimées via cascade SQLAlchemy
    - Fichiers audio session (`data/audio/sessions/{spotify_id}/`) effacés
    - Si target_kind='spotify_track' et la track n'est référencée par aucune
      autre session active ni aucune playlist → la track est aussi supprimée
      (TrackOverride, TrackAnalysis, fichier audio cache)
    """
    sess = db.scalar(
        select(CreativeSession).where(CreativeSession.spotify_id == spotify_id),
    )
    if sess is None:
        raise HTTPException(
            status_code=404, detail=f"Session {spotify_id!r} introuvable",
        )

    # Cleanup track orpheline (avant le delete pour pouvoir exclure cette session)
    if sess.target_kind == "spotify_track":
        _delete_orphan_track_if_unused(db, sess.target_ref, data_dir, sess.id)

    # Cleanup fichiers audio des versions
    audio_dir = data_dir / "audio" / "sessions" / sess.spotify_id
    if audio_dir.is_dir():
        shutil.rmtree(audio_dir, ignore_errors=True)

    # Hard delete (cascade auto sur SessionVersion via relationship)
    db.delete(sess)
    db.commit()
