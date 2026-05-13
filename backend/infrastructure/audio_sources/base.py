"""Interface des sources audio (Strategy pattern via Protocol).

Une source audio est tout objet exposant `download(...)` avec la bonne
signature. Pas besoin d'héritage explicite : duck typing structurel via
typing.Protocol. `@runtime_checkable` autorise `isinstance(obj, AudioSource)`
si on en a besoin.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class AudioSourceError(Exception):
    """Erreur générique d'une source audio."""


class TrackNotFoundError(AudioSourceError):
    """Aucun match audio trouvé pour le track demandé."""


class AudioSourceRateLimited(AudioSourceError):
    """La source nous bloque temporairement (429, captcha, ban IP, ...)."""


@runtime_checkable
class AudioSource(Protocol):
    """Interface structurelle des sources de téléchargement audio."""

    def download(
        self,
        spotify_id: str,
        title: str,
        artist: str,
        duration_ms: int | None = None,
    ) -> Path:
        """Télécharge l'audio dans le cache local et retourne le chemin du fichier.

        Args:
            spotify_id: ID Spotify, sert de clé de cache disque.
            title: Titre du morceau (utilisé pour la recherche).
            artist: Artiste(s) (utilisé pour la recherche).
            duration_ms: Durée Spotify, utilisée pour valider que le résultat
                trouvé correspond bien au track demandé.

        Returns:
            Path absolu du fichier audio décodé sur disque.

        Raises:
            TrackNotFoundError: aucun match acceptable trouvé.
            AudioSourceRateLimited: la source nous bloque temporairement.
            AudioSourceError: autre erreur (réseau, postprocessing, ...).
        """
        ...
