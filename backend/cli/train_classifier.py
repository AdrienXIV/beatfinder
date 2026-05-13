"""CLI : entraîne le classifier de style sur les playlists labelisées.

Mapping des playlists d'entraînement → style. Édite ci-dessous pour ajouter de
nouvelles classes (drill, lo-fi, ...) quand tu auras analysé les playlists
correspondantes via `python -m backend.cli.pipeline "<spotify_url>"`.

Usage :
    .venv/bin/python -m backend.cli.train_classifier
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from sqlalchemy import select

from backend.config import get_settings
from backend.db import init_db, make_engine, make_session_factory
from backend.domain.models import PlaylistTrack, Track, TrackAnalysis
from backend.services.style_classifier import (
    extract_features,
    save_model,
    train,
)

# Mapping playlist_spotify_id → label de classe.
# Ajoute une entrée quand tu analyses une nouvelle playlist de référence.
LABEL_MAPPING: dict[str, str] = {
    "0AxKYXcQKwLN04Ok73L8y6": "rap-fr",  # Top Rap FR Beatfinder
    "3eOWf5up5SwXoh3uh2tghA": "rap-us",  # Top Rap US 2026
}


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )
    log = logging.getLogger("train_classifier")

    settings = get_settings()
    engine = init_db(make_engine())
    SessionFactory = make_session_factory(engine)

    log.info("Labels configurés : %s", LABEL_MAPPING)

    samples: list[tuple] = []
    label_counts: dict[str, int] = {}
    skipped = 0

    with SessionFactory() as session:
        from backend.domain.models import Playlist

        for spotify_id, label in LABEL_MAPPING.items():
            playlist = session.scalar(
                select(Playlist).where(Playlist.spotify_id == spotify_id),
            )
            if playlist is None:
                log.warning("Playlist %s introuvable (label %s), skip", spotify_id, label)
                continue

            # Récupère toutes les tracks + leur dernière analyse
            pt_rows = session.scalars(
                select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id),
            ).all()
            for pt in pt_rows:
                analysis = session.scalar(
                    select(TrackAnalysis)
                    .where(TrackAnalysis.track_id == pt.track_id)
                    .order_by(TrackAnalysis.id.desc()),
                )
                if analysis is None:
                    skipped += 1
                    continue
                vec = extract_features(analysis.features_json)
                if vec is None:
                    skipped += 1
                    continue
                samples.append((vec, label))
                label_counts[label] = label_counts.get(label, 0) + 1

    log.info(
        "Samples extraits : %d (skipped %d). Distribution : %s",
        len(samples), skipped, label_counts,
    )

    if len(samples) < 10:
        log.error("Pas assez de samples (%d < 10). Analyse plus de playlists.", len(samples))
        return 1

    pipeline, result = train(samples)
    log.info("=== Training result ===")
    log.info("  classes      : %s", result.classes)
    log.info("  n_samples    : %d", result.n_samples)
    log.info("  CV accuracy  : %.3f ± %.3f", result.cv_accuracy_mean, result.cv_accuracy_std)
    log.info("  Top 5 features importance :")
    for i, (feat, imp) in enumerate(list(result.feature_importance.items())[:5]):
        log.info("    %d. %-35s %.3f", i + 1, feat, imp)

    model_dir = settings.data_dir / "models"
    save_model(pipeline, result, model_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
