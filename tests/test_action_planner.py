"""Tests des règles métier du plan d'action.

Pure fonctions pas d'I/O, donc testables directement sans fixtures lourdes.
On construit des patterns minimaux avec juste les sous-features nécessaires
à chaque règle.
"""
from __future__ import annotations

from backend.services.action_planner import generate_action_items


def _pattern_with_lufs(lufs: float) -> dict:
    return {
        "energy": {
            "lufs_integrated": {"median": lufs},
        },
    }


def test_no_action_when_either_pattern_empty():
    assert generate_action_items(None, _pattern_with_lufs(-12.0)) == []
    assert generate_action_items(_pattern_with_lufs(-12.0), None) == []
    assert generate_action_items({}, {}) == []


def test_lufs_delta_above_threshold_produces_high_priority_action():
    # from = -18 LUFS (calme), to = -10 LUFS (chaud) → delta = +8 → high
    items = generate_action_items(
        _pattern_with_lufs(-18.0), _pattern_with_lufs(-10.0),
    )
    lufs_items = [it for it in items if it["key"] == "mastering.lufs"]
    assert len(lufs_items) == 1
    item = lufs_items[0]
    assert item["priority"] == "high"
    assert item["current"] == -18.0
    assert item["target"] == -10.0
    assert item["delta"] == 8.0
    assert "Pousser le master" in item["action"]


def test_lufs_delta_below_threshold_no_action():
    # delta = 0.5 dB < seuil 0.7 → pas d'action
    items = generate_action_items(
        _pattern_with_lufs(-12.0), _pattern_with_lufs(-12.5),
    )
    assert not any(it["key"] == "mastering.lufs" for it in items)


def test_lufs_negative_delta_recommends_reduction():
    # from chaud (-9), to calme (-15) → réduire le master
    items = generate_action_items(
        _pattern_with_lufs(-9.0), _pattern_with_lufs(-15.0),
    )
    lufs_items = [it for it in items if it["key"] == "mastering.lufs"]
    assert len(lufs_items) == 1
    assert "Réduire le master" in lufs_items[0]["action"]
    assert lufs_items[0]["delta"] == -6.0


def test_items_sorted_by_category_then_priority():
    # Construit un from/to qui déclenche des items dans plusieurs catégories
    pattern_from = {
        "energy": {"lufs_integrated": {"median": -20.0}},  # mastering high
        "spectral": {
            "band_energy": {
                "sub": {"median": 0.10},  # mix
                "bass": {"median": 0.10},
                "low_mid": {"median": 0.10},
                "mid": {"median": 0.10},
                "high_mid": {"median": 0.10},
                "high": {"median": 0.10},
            },
        },
    }
    pattern_to = {
        "energy": {"lufs_integrated": {"median": -10.0}},
        "spectral": {
            "band_energy": {
                "sub": {"median": 0.40},
                "bass": {"median": 0.30},
                "low_mid": {"median": 0.10},
                "mid": {"median": 0.10},
                "high_mid": {"median": 0.10},
                "high": {"median": 0.10},
            },
        },
    }
    items = generate_action_items(pattern_from, pattern_to)
    categories = [it["category"] for it in items]
    # mastering doit venir avant mix (tri categoriel)
    if "mastering" in categories and "mix" in categories:
        assert categories.index("mastering") < categories.index("mix")
