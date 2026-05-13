"""Adaptateurs vers les systèmes externes — I/O réseau / disque / API tierces.

Composé des modules :
- `spotify_client` : wrapper Spotify Web API (OAuth)
- `settings_store` : persistence préférences utilisateur (JSON)
- `audio_sources/` : sources de téléchargement audio (YouTube, Deezer V2)
"""
from __future__ import annotations
