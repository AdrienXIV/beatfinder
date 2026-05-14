"""Génération du brief de production.

Split en sous-modules pour rester lisible :
- `_helpers.py` : constantes, helpers d'accès dict, interprétations qualitatives.
- `_analytics.py` : fit_score, détection bimodale, etc.
- `_recommendations.py` : bullets "À copier" / "À éviter" + actions EQ.
- `brief.py` : rendu markdown principal.

API publique : `generate_brief`. Re-exportée pour préserver l'import historique
`from backend.report_generator import generate_brief`.
"""
from __future__ import annotations

from .brief import generate_brief

__all__ = ["generate_brief"]
