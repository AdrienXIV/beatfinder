"""Services métier — pure logique applicative, pas d'I/O direct.

Composé des modules :
- `action_planner` : règles de génération du plan d'action source→target
- `pattern_extractor` : agrégation des features track → pattern playlist
- `cache_inspector` : audit + flush des caches FS/DB
"""
from __future__ import annotations
