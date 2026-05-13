"""Génération du brief de production + export CSV.

Split en sous-modules pour rester lisible :
- `_helpers.py` : constantes, helpers d'accès dict, interprétations qualitatives.
- `_analytics.py` : fit_score, détection bimodale, etc.
- `_recommendations.py` : bullets "À copier" / "À éviter" + actions EQ.
- `brief.py` : rendu markdown principal.
- `csv_export.py` : export tabulaire.

API publique : `generate_brief`, `generate_csv`. Re-exportées pour préserver
l'import historique `from backend.report_generator import generate_brief`.
"""
from __future__ import annotations

from .brief import generate_brief
from .csv_export import generate_csv

__all__ = ["generate_brief", "generate_csv"]
