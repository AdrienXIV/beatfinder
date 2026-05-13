"""Classifier de style (rap-fr / rap-us / trap / ...) sur les features audio.

Pipeline simple : RandomForest entraîné sur les features track-level extraites
depuis les playlists analysées. Chaque playlist sert de "label" → toutes ses
tracks sont labelisées avec le nom du label associé.

Pour entraîner : `python -m backend.cli.train_classifier`
Pour prédire   : `predict(pattern_or_features) -> list[Prediction]`

Le modèle est persisté en joblib dans `data/models/style_classifier.joblib`.
Re-entraînable à volonté quand de nouvelles playlists sont analysées.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)


# Features extraites par track (15 valeurs). Ordre fixe — ne pas changer
# sans re-train, sinon la persistance casse.
FEATURE_KEYS: tuple[tuple[str, ...], ...] = (
    ("tempo", "bpm"),
    ("tempo", "onset_density"),
    ("tempo", "beat_consistency"),
    ("energy", "lufs_integrated"),
    ("energy", "true_peak_db"),
    ("energy", "crest_factor_db"),
    ("energy", "dynamic_range_db"),
    ("spectral", "centroid_hz"),
    ("spectral", "rolloff85_hz"),
    ("spectral", "band_energy", "sub"),
    ("spectral", "band_energy", "bass"),
    ("spectral", "band_energy", "low_mid"),
    ("spectral", "band_energy", "mid"),
    ("spectral", "band_energy", "high_mid"),
    ("spectral", "band_energy", "high"),
)


@dataclass(slots=True, frozen=True)
class Prediction:
    style: str
    probability: float


@dataclass(slots=True, frozen=True)
class TrainingResult:
    n_samples: int
    n_classes: int
    classes: list[str]
    cv_accuracy_mean: float
    cv_accuracy_std: float
    feature_importance: dict[str, float]


def _walk(d: dict | None, *path: str) -> Any:
    val: Any = d
    for p in path:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
        if val is None:
            return None
    return val


def extract_features(features_json: dict) -> np.ndarray | None:
    """Extrait le vecteur de features d'une track. None si une feature critique manque."""
    vec: list[float] = []
    for path in FEATURE_KEYS:
        val = _walk(features_json, *path)
        if not isinstance(val, (int, float)) or not np.isfinite(val):
            return None
        vec.append(float(val))
    return np.array(vec, dtype=np.float64)


def extract_features_from_pattern(pattern: dict) -> np.ndarray | None:
    """Extrait le vecteur de features depuis un pattern agrégé (playlist ou preset).

    Le pattern a la forme `{"tempo": {"bpm": {"median": X, "std": ...}, ...}, ...}`.
    On cherche `.median` au lieu de la valeur directe (qui est le format track).
    """
    vec: list[float] = []
    for path in FEATURE_KEYS:
        val = _walk(pattern, *path, "median")
        if not isinstance(val, (int, float)) or not np.isfinite(val):
            return None
        vec.append(float(val))
    return np.array(vec, dtype=np.float64)


def feature_labels() -> list[str]:
    """Labels lisibles des features (pour explain l'importance)."""
    return [".".join(path) for path in FEATURE_KEYS]


def train(
    samples: list[tuple[np.ndarray, str]],
    *,
    n_estimators: int = 200,
    random_state: int = 42,
) -> tuple[Pipeline, TrainingResult]:
    """Entraîne un RandomForest sur les samples [(features, label)].

    Retourne le pipeline (scaler + classifier) et un résumé d'évaluation
    via cross-validation 5-fold (ou moins si moins de samples).
    """
    if len(samples) < 10:
        raise ValueError(
            f"Pas assez de samples pour entraîner ({len(samples)} < 10 minimum)",
        )

    X = np.vstack([s[0] for s in samples])
    y = np.array([s[1] for s in samples])
    classes = sorted(set(y.tolist()))
    if len(classes) < 2:
        raise ValueError(f"Au moins 2 classes requises, got {classes}")

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1,
            class_weight="balanced",
        )),
    ])

    cv_n = min(5, min(np.bincount([classes.index(c) for c in y])))
    if cv_n >= 2:
        scores = cross_val_score(pipeline, X, y, cv=cv_n, scoring="accuracy")
        cv_mean = float(np.mean(scores))
        cv_std = float(np.std(scores))
        log.info(
            "Cross-val accuracy (k=%d) : %.3f ± %.3f",
            cv_n, cv_mean, cv_std,
        )
    else:
        cv_mean = float("nan")
        cv_std = float("nan")
        log.warning("Pas assez de samples par classe pour CV (min=%d)", cv_n)

    pipeline.fit(X, y)

    clf: RandomForestClassifier = pipeline.named_steps["clf"]
    importances = dict(zip(feature_labels(), clf.feature_importances_.tolist(), strict=True))

    result = TrainingResult(
        n_samples=len(samples),
        n_classes=len(classes),
        classes=classes,
        cv_accuracy_mean=cv_mean,
        cv_accuracy_std=cv_std,
        feature_importance=dict(sorted(importances.items(), key=lambda kv: -kv[1])),
    )
    return pipeline, result


def save_model(pipeline: Pipeline, result: TrainingResult, model_dir: Path) -> Path:
    """Sauve le modèle + meta dans model_dir/style_classifier.joblib."""
    model_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pipeline": pipeline,
        "feature_keys": FEATURE_KEYS,
        "result": {
            "n_samples": result.n_samples,
            "classes": result.classes,
            "cv_accuracy_mean": result.cv_accuracy_mean,
            "cv_accuracy_std": result.cv_accuracy_std,
            "feature_importance": result.feature_importance,
        },
    }
    path = model_dir / "style_classifier.joblib"
    joblib.dump(payload, path)
    log.info("Modèle sauvé : %s (%d KB)", path, path.stat().st_size // 1024)
    return path


def load_model(model_dir: Path) -> tuple[Pipeline, dict] | None:
    """Charge le modèle persisté. None si absent."""
    path = model_dir / "style_classifier.joblib"
    if not path.exists():
        return None
    try:
        payload = joblib.load(path)
        return payload["pipeline"], payload["result"]
    except (KeyError, ValueError, OSError) as e:
        log.warning("Modèle corrompu %s : %s", path, e)
        return None


def predict(pipeline: Pipeline, features: np.ndarray) -> list[Prediction]:
    """Prédit le style pour un vecteur de features. Retourne toutes les classes
    avec leur probabilité, triées du plus probable au moins probable."""
    if features.ndim == 1:
        features = features.reshape(1, -1)
    probas = pipeline.predict_proba(features)[0]
    classes = pipeline.classes_
    pairs = sorted(
        zip(classes.tolist(), probas.tolist(), strict=True),
        key=lambda kv: -kv[1],
    )
    return [Prediction(style=str(s), probability=float(p)) for s, p in pairs]
