"""Type aliases partagés entre modules backend.

Centralise les signatures de callbacks utilisées par le pipeline d'analyse
et le système de jobs (UI progress reporting). Évite la duplication.
"""
from __future__ import annotations

from collections.abc import Callable

# Callback de progression : (current, total, label) → None.
# `current` est un float pour permettre la progression fractionnelle intra-track
# (l'analyzer emit 14× par track : 7 étapes × 2 sub-events "start"/"done").
ProgressCallback = Callable[[float, int, str], None]

# Callback de log textuel : (message,) → None.
LogCallback = Callable[[str], None]

# Callback d'étape granulaire pour analyze_track :
# (step_key, step_label, fraction ∈ [0, 1]) → None.
StepCallback = Callable[[str, str, float], None]
