"""Wrapper spotipy authentifié en Authorization Code Flow (SpotifyOAuth).

Depuis novembre 2024, Spotify a restreint l'accès à `/playlists/{id}/items` en
Client Credentials pour les nouvelles apps en Development Mode → on attaque
direct en Authorization Code Flow avec loopback redirect.

Première exécution :
  - Le navigateur s'ouvre sur la page d'accord OAuth Spotify
  - Tu acceptes les permissions
  - Spotify redirige sur http://127.0.0.1:8888/callback
  - Spotipy capture le code via un serveur local éphémère (1 requête, port 8888)
  - Le token est mis en cache dans .spotify_cache (gitignored)
  - Refresh automatique via le refresh_token (cache mis à jour à chaque refresh)
"""
from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Final

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from backend.config import get_settings

logger = logging.getLogger(__name__)


class EditorialPlaylistError(RuntimeError):
    """Playlist éditoriale Spotify inaccessible via Web API.

    Depuis le 27 novembre 2024 (Spotify Developer changelog), les apps en
    Development Mode ou créées après cette date ne peuvent plus lister les
    tracks des "Algorithmic and Spotify-owned editorial playlists" (incluant
    les curateurs partenaires officiels — Filtr, Topsify, Digster, etc.).
    Le `/playlists/{id}` (meta) reste accessible, mais `/playlists/{id}/tracks`
    retourne 403 et le `track_count` du meta est forcé à 0.
    """


class PlaylistAccessError(RuntimeError):
    """Playlist Spotify inaccessible (privée d'un autre user, supprimée, etc.)."""

PLAYLIST_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:spotify:playlist:|open\.spotify\.com/playlist/)([A-Za-z0-9]{22})"
)

DEFAULT_SCOPE: Final[str] = "playlist-read-private playlist-read-collaborative"
DEFAULT_REDIRECT_URI: Final[str] = "http://127.0.0.1:8888/callback"


@dataclass(slots=True)
class TrackMeta:
    """Métadonnées minimales d'un track Spotify exploitable pour l'analyse."""

    spotify_id: str
    title: str
    artist: str
    duration_ms: int
    release_date: str | None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class PlaylistMeta:
    """Métadonnées d'une playlist Spotify (sans la liste des tracks)."""

    spotify_id: str
    name: str
    owner_id: str
    owner_display_name: str | None
    description: str | None
    track_count: int

    def as_dict(self) -> dict:
        return asdict(self)


class SpotifyClient:
    """Client Spotipy en Authorization Code Flow.

    Capable de lire toutes les playlists publiques + les playlists privées et
    collaboratives de l'utilisateur authentifié.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        cache_path: str | os.PathLike[str] | None = None,
        scope: str = DEFAULT_SCOPE,
        open_browser: bool = True,
    ) -> None:
        # Priorité : arguments explicites → settings.json → .env → defaults.
        # `load_settings()` lit déjà `.env` (via backend.config.get_settings),
        # donc pas besoin de re-faire os.getenv ici.
        if not client_id or not client_secret or not redirect_uri:
            from backend.infrastructure.settings_store import load_settings
            stored = load_settings()
            client_id = client_id or stored.spotify.client_id
            client_secret = client_secret or stored.spotify.client_secret
            redirect_uri = (
                redirect_uri or stored.spotify.redirect_uri or DEFAULT_REDIRECT_URI
            )
        if not client_id or not client_secret:
            raise RuntimeError(
                "Spotify non configuré. Va dans Paramètres pour saisir "
                "ton CLIENT_ID + CLIENT_SECRET (https://developer.spotify.com)."
            )
        # Cache OAuth dans data_dir/.spotify_cache pour rester portable
        # (sinon créé dans cwd, casse en mode binaire desktop).
        settings = get_settings()
        if cache_path:
            resolved_cache = str(cache_path)
        elif settings.spotify_cache_path:
            resolved_cache = str(settings.spotify_cache_path)
        else:
            resolved_cache = str(settings.data_dir / ".spotify_cache")
        auth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            cache_path=resolved_cache,
            open_browser=open_browser,
        )
        self._sp = spotipy.Spotify(auth_manager=auth, retries=3, status_retries=3)

    @staticmethod
    def parse_playlist_id(url_or_id: str) -> str:
        """Extrait l'ID base62 22 caractères depuis URL, URI ou ID brut."""
        candidate = url_or_id.strip()
        if re.fullmatch(r"[A-Za-z0-9]{22}", candidate):
            return candidate
        m = PLAYLIST_ID_RE.search(candidate)
        if not m:
            raise ValueError(f"Playlist Spotify invalide : {url_or_id!r}")
        return m.group(1)

    def get_playlist_meta(self, url_or_id: str) -> PlaylistMeta:
        """Métadonnées (name, owner, description, count) d'une playlist."""
        playlist_id = self.parse_playlist_id(url_or_id)
        p = self._sp.playlist(
            playlist_id,
            fields="id,name,description,owner(id,display_name),tracks(total)",
        )
        owner = p.get("owner") or {}
        return PlaylistMeta(
            spotify_id=p["id"],
            name=p.get("name") or "",
            owner_id=owner.get("id") or "",
            owner_display_name=owner.get("display_name"),
            description=p.get("description"),
            track_count=int((p.get("tracks") or {}).get("total", 0)),
        )

    def get_playlist_tracks(self, url_or_id: str) -> list[TrackMeta]:
        """Tracks exploitables d'une playlist (skip locals, episodes, removed).

        Note : Spotify a renommé le champ `items[].track` en `items[].item` dans
        la réponse de `/playlists/{id}/items` quand `additional_types` est passé.
        On lit donc `entry["item"]`, et `is_local` reste au niveau du wrapper.
        """
        playlist_id = self.parse_playlist_id(url_or_id)
        tracks: list[TrackMeta] = []
        for entry in self._iter_playlist_items(playlist_id):
            if entry.get("is_local"):
                continue
            track = entry.get("item") or entry.get("track")  # back-compat
            if not track or track.get("type") != "track":
                continue
            spotify_id = track.get("id")
            if not spotify_id:
                continue
            artists = ", ".join(
                a["name"] for a in track.get("artists", []) if a.get("name")
            )
            tracks.append(
                TrackMeta(
                    spotify_id=spotify_id,
                    title=track["name"],
                    artist=artists,
                    duration_ms=int(track["duration_ms"]),
                    release_date=(track.get("album") or {}).get("release_date"),
                )
            )
        logger.info(
            "Playlist %s : %d tracks exploitables (locals/episodes ignorés)",
            playlist_id, len(tracks),
        )
        return tracks

    def _iter_playlist_items(self, playlist_id: str) -> Iterator[dict]:
        """Pagination 100/page sur l'endpoint playlist_items.

        Raise EditorialPlaylistError / PlaylistAccessError si Spotify renvoie
        un 403 sur l'endpoint /tracks (cas typique des playlists éditoriales
        depuis nov 2024 — voir docstring EditorialPlaylistError).
        """
        offset = 0
        limit = 100
        fields = (
            "items(is_local,item(id,name,artists(name),duration_ms,type,"
            "album(release_date))),next"
        )
        while True:
            try:
                page = self._sp.playlist_items(
                    playlist_id,
                    limit=limit,
                    offset=offset,
                    fields=fields,
                    additional_types=("track",),
                )
            except SpotifyException as exc:
                if exc.http_status == 403:
                    self._raise_403_diagnostic(playlist_id, exc)
                raise
            yield from page.get("items", [])
            if not page.get("next"):
                break
            offset += limit

    def _raise_403_diagnostic(
        self, playlist_id: str, original: SpotifyException
    ) -> None:
        """Discrimine 403 'playlist éditoriale' vs 403 'accès refusé générique'.

        Pattern signature d'une playlist éditoriale post-27/11/2024 :
          - GET /playlists/{id}         → 200 OK
          - GET /playlists/{id}/tracks  → 403
          - meta.tracks.total           → 0 (Spotify masque le compteur)

        Pour un autre 403 (playlist privée d'un user tiers), le meta plante
        aussi avec 403/404.
        """
        try:
            meta = self.get_playlist_meta(playlist_id)
        except SpotifyException:
            raise PlaylistAccessError(
                f"Playlist {playlist_id} inaccessible — privée, supprimée, "
                f"ou owner restreint. Vérifie que la playlist est publique "
                f"et accessible depuis ton compte Spotify."
            ) from original
        raise EditorialPlaylistError(
            f"Playlist '{meta.name}' (owner: {meta.owner_display_name or meta.owner_id}) "
            f"est une playlist éditoriale Spotify. Depuis le 27/11/2024, "
            f"l'API Web bloque l'accès aux tracks de ces playlists pour les apps "
            f"en Development Mode. Solution : clone la playlist dans une playlist "
            f"perso à toi via le client Spotify (clic droit sur la playlist → "
            f"'Ajouter à une autre playlist'), puis utilise l'URL de ta copie. "
            f"Doc : https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api"
        ) from original
