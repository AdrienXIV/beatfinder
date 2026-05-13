"""DeezerPreviewSource : preview API officielle 30s (V2 monétisable).

Reporté V2 : Deezer expose des previews 30s via leur API publique sans clé.
Avantage : 100% légal pour usage commercial (preview seulement, pas le full
track). Inconvénient : 30s seulement, suffisant pour BPM/tonalité/spectre
mais pas pour structure/segments.

À implémenter quand on sortira de l'usage perso.
"""
from __future__ import annotations
