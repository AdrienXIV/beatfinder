"""Routes FastAPI actions (V1.7+) — plan d'action entre 2 sources audio.

Source et cible peuvent être :
- une `playlist` (compare son pattern agrégé) — id = Spotify playlist ID
- une `track` individuelle — id = Spotify track ID
- un `preset` industry-standard (Rap FR, Rap US, ...) — id = `preset:KEY`

  GET    /actions?from={id}&to={id}                            plan + cache file
  DELETE /actions?from={id}&to={id}                            invalide le cache
  GET    /actions/compared-with?from={id}                      targets déjà comparées depuis from
  GET    /actions/sources                                      tous les from_id qui ont au moins
                                                               1 comparaison (pour pastilles UI)
  GET    /actions/presets                                      liste des presets utilisables comme cible
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.api.deps import get_data_dir, get_session
from backend.api.schemas import (
    ActionPlanOut,
    ComparedSourceOut,
    ComparedTargetOut,
    StylePredictionItemOut,
    StylePredictionOut,
    ThresholdPresetOut,
)
from backend.local_projects import brief_filename
from backend.services.action_planner import generate_action_items
from backend.services import style_classifier
from backend.services.daw_export import (
    build_master_chain,
    generate_ableton_adg,
    generate_markdown,
)
from backend.services.source_loader import PatternSource, load_pattern_source
from backend.services.threshold_presets import PRESET_ID_PREFIX, list_presets

log = logging.getLogger("backend.api.routes_actions")

router = APIRouter(tags=["actions"])

SessionDep = Annotated[Session, Depends(get_session)]
DataDirDep = Annotated[Path, Depends(get_data_dir)]


# Source resolution centralisée dans backend.services.source_loader
_load_source = load_pattern_source
_PatternSource = PatternSource


def _cache_path(data_dir: Path, from_id: str, to_id: str) -> Path:
    fname = f"{brief_filename(from_id)}__vs__{brief_filename(to_id)}.json"
    return data_dir / "reports" / "actions" / fname


def _extract_bands(pattern: dict) -> dict[str, float]:
    """Extrait les médianes par bande spectrale (ratio 0-1) du pattern."""
    bands_node = (pattern.get("spectral", {}) or {}).get("band_energy", {}) or {}
    out: dict[str, float] = {}
    for band in ("sub", "bass", "low_mid", "mid", "high_mid", "high"):
        median = (bands_node.get(band) or {}).get("median")
        if isinstance(median, (int, float)):
            out[band] = float(median)
    return out


def _is_cache_valid(payload: dict, src: _PatternSource, tgt: _PatternSource) -> bool:
    """Le cache reste valide tant que les pattern_id (côté playlist) n'ont pas changé.

    Pour les tracks, pas de pattern_id : on suppose qu'une track ne change pas
    silencieusement (toute réanalyse passe par une route explicite qui crée une
    nouvelle TrackAnalysis, mais on n'invalide pas automatiquement le plan d'action).
    Si Adrien réanalyse une track, il peut hit le bouton Régénérer côté UI.
    """
    return (
        payload.get("from_pattern_id") == src.pattern_id
        and payload.get("to_pattern_id") == tgt.pattern_id
    )


@router.get("/actions", response_model=ActionPlanOut)
def get_action_plan(
    session: SessionDep,
    data_dir: DataDirDep,
    from_id: Annotated[str, Query(alias="from", description="Source ID (playlist or track)")],
    to: Annotated[str, Query(description="Target ID (playlist or track)")],
    regenerate: bool = False,
) -> ActionPlanOut:
    """Renvoie la checklist d'actions pour rapprocher `from` de `to`.

    `from` et `to` peuvent être chacun un Spotify playlist ID OU un track spotify_id
    (résolution auto via lookup DB). Cache fichier `data/reports/actions/{from}__vs__{to}.json`.
    """
    if from_id == to:
        raise HTTPException(
            status_code=400, detail="Cannot compare a source with itself",
        )

    src = _load_source(session, from_id)
    tgt = _load_source(session, to)

    cache = _cache_path(data_dir, from_id, to)
    if cache.exists() and not regenerate:
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
            if _is_cache_valid(payload, src, tgt):
                payload["cached"] = True
                return ActionPlanOut(**payload)
        except (json.JSONDecodeError, OSError, ValueError):
            log.warning("Corrupt action plan cache %s, regenerating", cache)

    items = generate_action_items(src.pattern, tgt.pattern)

    out = ActionPlanOut(
        from_id=src.id,
        from_name=src.name,
        from_n_tracks=src.n_tracks,
        to_id=tgt.id,
        to_name=tgt.name,
        to_n_tracks=tgt.n_tracks,
        from_pattern_id=src.pattern_id,
        to_pattern_id=tgt.pattern_id,
        from_bands=_extract_bands(src.pattern),
        to_bands=_extract_bands(tgt.pattern),
        items=items,
        generated_at=datetime.now(UTC),
        cached=False,
    )

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(out.model_dump_json(), encoding="utf-8")
    return out


@router.get("/actions/master-chain.md")
def export_master_chain_md(
    session: SessionDep,
    data_dir: DataDirDep,
    from_id: Annotated[str, Query(alias="from")],
    to: Annotated[str, Query()],
) -> Response:
    """Génère un guide markdown de chaîne master (EQ + Compressor + Limiter)
    à partir du plan d'action `from → to`. Universel : Live/FL/Logic/Reaper."""
    plan = get_action_plan(session, data_dir, from_id, to)
    chain = build_master_chain(plan)
    md = generate_markdown(chain)
    filename = f"{brief_filename(from_id)}__vs__{brief_filename(to)}-master-chain.md"
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/actions/master-chain.adg")
def export_master_chain_adg(
    session: SessionDep,
    data_dir: DataDirDep,
    from_id: Annotated[str, Query(alias="from")],
    to: Annotated[str, Query()],
) -> Response:
    """Génère un .adg Ableton (XML gzippé) de la chaîne master.

    EXPÉRIMENTAL : rack vide nommé avec annotation des paramètres. À remplir
    manuellement dans Live. Si Live refuse l'ouverture, utilise le .md.
    """
    plan = get_action_plan(session, data_dir, from_id, to)
    chain = build_master_chain(plan)
    blob = generate_ableton_adg(chain)
    filename = f"{brief_filename(from_id)}__vs__{brief_filename(to)}-master-chain.adg"
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/actions", status_code=204)
def delete_action_plan(
    data_dir: DataDirDep,
    from_id: Annotated[str, Query(alias="from")],
    to: Annotated[str, Query()],
) -> Response:
    """Invalide le cache pour la paire (from, to). No-op si absent."""
    cache = _cache_path(data_dir, from_id, to)
    if cache.exists():
        cache.unlink()
        log.info("Deleted action plan cache %s", cache.name)
    return Response(status_code=204)


@router.get("/actions/compared-with", response_model=list[ComparedTargetOut])
def list_compared_targets(
    data_dir: DataDirDep,
    from_id: Annotated[str, Query(alias="from")],
) -> list[ComparedTargetOut]:
    """Liste les targets déjà explorées depuis `from_id` (playlist OU track)."""
    actions_dir = data_dir / "reports" / "actions"
    if not actions_dir.is_dir():
        return []

    prefix = f"{brief_filename(from_id)}__vs__"
    out: list[ComparedTargetOut] = []
    for path in actions_dir.glob(f"{prefix}*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if payload.get("from_id") != from_id:
            continue
        items = payload.get("items") or []
        generated_at_raw = payload.get("generated_at")
        try:
            generated_at = (
                datetime.fromisoformat(generated_at_raw.replace("Z", "+00:00"))
                if isinstance(generated_at_raw, str)
                else datetime.now(UTC)
            )
        except ValueError:
            generated_at = datetime.now(UTC)
        out.append(ComparedTargetOut(
            target_id=payload.get("to_id", ""),
            target_name=payload.get("to_name", ""),
            target_n_tracks=int(payload.get("to_n_tracks", 0)),
            n_items=len(items),
            generated_at=generated_at,
        ))
    out.sort(key=lambda c: c.generated_at, reverse=True)
    return out


@router.get("/style-predict", response_model=StylePredictionOut)
def predict_style_endpoint(
    session: SessionDep,
    data_dir: DataDirDep,
    from_id: Annotated[str, Query(alias="from", description="ID source (playlist/track/preset)")],
) -> StylePredictionOut:
    """Prédit le style musical d'un pattern (playlist, track ou preset).

    Le modèle est entraîné via `python -m backend.cli.train_classifier`.
    Retourne 503 si le modèle n'a pas encore été entraîné.
    """
    model_dir = data_dir / "models"
    loaded = style_classifier.load_model(model_dir)
    if loaded is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Classifier non entraîné. Lance "
                "`python -m backend.cli.train_classifier` après avoir analysé "
                "au moins 2 playlists labellisées."
            ),
        )
    pipeline, meta = loaded

    src = load_pattern_source(session, from_id)
    features = style_classifier.extract_features_from_pattern(src.pattern)
    if features is None:
        raise HTTPException(
            status_code=409,
            detail=f"Features incomplètes pour {from_id!r}",
        )

    predictions = style_classifier.predict(pipeline, features)
    return StylePredictionOut(
        source_id=src.id,
        source_name=src.name,
        predictions=[
            StylePredictionItemOut(style=p.style, probability=p.probability)
            for p in predictions
        ],
        model_classes=meta["classes"],
        model_cv_accuracy=meta["cv_accuracy_mean"],
    )


@router.get("/actions/presets", response_model=list[ThresholdPresetOut])
def list_threshold_presets() -> list[ThresholdPresetOut]:
    """Liste tous les presets industry-standard utilisables comme cible.

    Le `target_id` retourné est l'ID complet (`preset:KEY`) à passer dans
    `GET /actions?from=...&to=...` côté UI.
    """
    return [
        ThresholdPresetOut(
            key=p.key,
            target_id=f"{PRESET_ID_PREFIX}{p.key}",
            name=p.name,
            description=p.description,
            n_tracks_source=p.n_tracks_source,
            source_playlist_name=p.source_playlist_name,
        )
        for p in list_presets()
    ]


@router.get("/actions/sources", response_model=list[ComparedSourceOut])
def list_action_sources(data_dir: DataDirDep) -> list[ComparedSourceOut]:
    """Liste tous les from_id qui ont au moins 1 plan d'action généré.

    Utilisé par le frontend pour afficher des pastilles "déjà comparé" sur les
    rows tracks de la page playlist (en 1 seul appel au lieu de N).
    """
    actions_dir = data_dir / "reports" / "actions"
    if not actions_dir.is_dir():
        return []

    counts: dict[str, int] = {}
    for path in actions_dir.glob("*__vs__*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        from_id = payload.get("from_id")
        if isinstance(from_id, str) and from_id:
            counts[from_id] = counts.get(from_id, 0) + 1
    return [ComparedSourceOut(from_id=fid, n_targets=cnt) for fid, cnt in counts.items()]
