"""YouTubeSource : recherche + téléchargement audio via yt-dlp (Python module).

Stratégie de matching :
  1. ytsearch10 sur "artist title".
  2. Filtre les résultats avec mots-clés blacklist (live/cover/karaoke/sped up...).
  3. Si duration_ms est fourni, garde le résultat dont la durée est la plus proche
     dans la tolérance (±5s ou ±10%, le plus permissif des deux).
  4. Si aucun candidat acceptable, retry avec `title` seul (sans artiste) — utile
     quand YouTube indexe l'upload sous "Title - Artist" au lieu de "Artist - Title".
  5. Sinon retourne le premier candidat non-blacklisté.

Cache : data/audio/{spotify_id}.mp3 (skip si déjà présent).
Dépendance système : ffmpeg (requis pour FFmpegExtractAudio postprocessor).
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

from .base import (
    AudioSourceError,
    AudioSourceRateLimited,
    TrackNotFoundError,
)

logger = logging.getLogger(__name__)

BLACKLIST_KEYWORDS = re.compile(
    r"\b(live|cover|karaok[ée]|instrumental|sped\s*up|slowed|reaction|"
    r"tutorial|8d|nightcore|reverb|mashup)\b",
    re.IGNORECASE,
)
DURATION_TOLERANCE_MS = 5_000
DURATION_TOLERANCE_PCT = 0.10


def _detect_js_runtimes() -> dict[str, dict]:
    """Détecte le JS runtime dispo pour yt-dlp (deno > bun > node).

    yt-dlp 2026.x demande un JS runtime pour extraire certains formats YouTube.
    Par défaut yt-dlp active uniquement `deno`. Cette fonction enrichit la liste
    avec node si présent dans PATH, ce qui évite le warning "deno required".
    Priorité : deno > bun > node (selon recommandation yt-dlp). On configure
    tous ceux trouvés ; yt-dlp utilisera le mieux supporté.
    """
    runtimes: dict[str, dict] = {}
    for name in ("deno", "bun", "node"):
        if shutil.which(name):
            runtimes[name] = {}
    if not runtimes:
        runtimes = {"deno": {}}  # défaut yt-dlp si rien trouvé
    return runtimes


_JS_RUNTIMES = _detect_js_runtimes()


def _locate_ffmpeg() -> str | None:
    """Trouve ffmpeg sur la machine et retourne le dossier qui le contient.

    yt-dlp accepte un dossier via `ffmpeg_location` (il y cherche ffmpeg ET
    ffprobe). Ordre de priorité :
      1. ffmpeg bundled à côté du binaire (cas .app macOS / AppImage Linux)
      2. Paths Homebrew standards macOS (/opt/homebrew/bin pour ARM,
         /usr/local/bin pour Intel) — utile car les .app GUI macOS héritent
         d'un PATH minimal sans /opt/homebrew/bin.
      3. shutil.which (PATH) — cas normal Linux/dev.
    """
    candidates: list[Path] = []

    # 1. Bundle local (sys.executable / .. )
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys.executable).parent
        candidates.append(bundle_dir / "ffmpeg")

    # 2. Paths absolus connus (utile sur macOS GUI où PATH est minimal)
    if sys.platform == "darwin":
        candidates.extend([
            Path("/opt/homebrew/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
        ])

    for ffmpeg_path in candidates:
        if ffmpeg_path.is_file():
            return str(ffmpeg_path.parent)

    # 3. PATH fallback
    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).parent)
    return None


_FFMPEG_LOCATION = _locate_ffmpeg()
if _FFMPEG_LOCATION:
    logger.info("ffmpeg détecté : %s", _FFMPEG_LOCATION)
else:
    logger.warning(
        "ffmpeg introuvable — l'extraction MP3 va échouer. "
        "Installe ffmpeg (apt install ffmpeg / brew install ffmpeg)."
    )


class YouTubeSource:
    """Source audio YouTube (V1, usage personnel uniquement).

    Satisfait le Protocol `backend.audio_sources.base.AudioSource` par duck typing.
    """

    def __init__(
        self,
        cache_dir: Path,
        *,
        search_results: int = 10,
        audio_quality: str = "320",
        cookies_file: str | os.PathLike[str] | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._search_results = search_results
        self._audio_quality = audio_quality
        self._cookies_file = str(cookies_file) if cookies_file else None

    def download(
        self,
        spotify_id: str,
        title: str,
        artist: str,
        duration_ms: int | None = None,
    ) -> Path:
        target = self.cache_dir / f"{spotify_id}.mp3"
        if target.exists():
            logger.debug("Cache hit %s", target.name)
            return target

        primary_query = f"{artist} {title}".strip()
        if not primary_query:
            raise TrackNotFoundError(f"Query vide pour spotify_id={spotify_id}")

        # 1er essai : "artist title". Si aucun candidat acceptable, retry avec
        # le titre seul (sans artiste) pour rattraper les uploads indexés
        # différemment (ex: "Title - Artist", "Title prod by X", etc.).
        queries = [primary_query]
        if title.strip() and title.strip() != primary_query:
            queries.append(title.strip())

        candidate: dict | None = None
        last_stats: dict[str, int] = {}
        tried: list[str] = []
        for q in queries:
            tried.append(q)
            try:
                entries = self._search(q)
            except (DownloadError, ExtractorError) as exc:
                raise self._classify_error(exc) from exc
            if not entries:
                last_stats = {"n_total": 0, "n_blacklist": 0, "n_out_of_duration": 0}
                continue
            candidate, last_stats = self._pick_candidate(
                entries, duration_ms=duration_ms, artist=artist,
            )
            if candidate is not None:
                break
            logger.info(
                "Retry recherche avec query simplifiée : query=%r n_total=%d "
                "rejets={blacklist:%d, hors-durée:%d}",
                q, last_stats.get("n_total", 0),
                last_stats.get("n_blacklist", 0),
                last_stats.get("n_out_of_duration", 0),
            )

        if candidate is None:
            n_total = last_stats.get("n_total", 0)
            if n_total == 0:
                raise TrackNotFoundError(
                    f"Aucun résultat YouTube pour : {primary_query} "
                    f"(queries essayées : {tried})"
                )
            raise TrackNotFoundError(
                f"Aucun match acceptable pour {primary_query} "
                f"(durée Spotify={duration_ms}ms, "
                f"{n_total} résultats inspectés sur la dernière query : "
                f"{last_stats.get('n_blacklist', 0)} blacklistés, "
                f"{last_stats.get('n_out_of_duration', 0)} hors-durée ; "
                f"queries essayées : {tried})."
            )

        video_url = candidate.get("url") or candidate.get("webpage_url")
        if not video_url:
            raise AudioSourceError(f"URL absente du candidat : {candidate}")

        try:
            self._download(video_url, target_no_ext=self.cache_dir / spotify_id)
        except (DownloadError, ExtractorError) as exc:
            raise self._classify_error(exc) from exc

        if not target.exists():
            raise AudioSourceError(
                f"Téléchargement réussi mais fichier MP3 absent : {target}"
            )
        logger.info("Téléchargé %s — %s -> %s", artist, title, target.name)
        return target

    def _search(self, query: str) -> list[dict]:
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "logger": _YTDLPLogger(),
            "js_runtimes": _JS_RUNTIMES,
        }
        if self._cookies_file:
            opts["cookiefile"] = self._cookies_file
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"ytsearch{self._search_results}:{query}", download=False
            )
        return list((info or {}).get("entries", []) or [])

    def _download(self, video_url: str, *, target_no_ext: Path) -> None:
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": f"{target_no_ext}.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self._audio_quality,
                }
            ],
            "logger": _YTDLPLogger(),
            "js_runtimes": _JS_RUNTIMES,
        }
        if _FFMPEG_LOCATION:
            opts["ffmpeg_location"] = _FFMPEG_LOCATION
        if self._cookies_file:
            opts["cookiefile"] = self._cookies_file
        with YoutubeDL(opts) as ydl:
            ydl.download([video_url])

    @staticmethod
    def _pick_candidate(
        entries: list[dict],
        *,
        duration_ms: int | None,
        artist: str = "",
    ) -> tuple[dict | None, dict[str, int]]:
        """Choisit le meilleur candidat + retourne un dict de stats de rejet.

        Tiers (du meilleur au pire) :
          0 — Chaîne "X - Topic" : upload auto-généré par YouTube depuis le master
              Spotify/distributeur. C'est l'audio identique au master Spotify (idéal).
          1 — Chaîne officielle ("Vevo", contient "official") : clip officiel,
              audio en général de bonne qualité mais potentiellement mastered différemment.
          2 — Chaîne de l'artiste lui-même (matching nom).
          3 — Reste (lyrics videos, fan uploads, instru/karaoke échappés au blacklist).

        À tier égal, on prend le plus proche en durée.

        Le 2e élément du tuple : `{"n_total", "n_blacklist", "n_out_of_duration"}`.
        Utilisé pour produire un message d'erreur informatif quand rien ne passe.
        """
        artist_primary = artist.split(",")[0].strip().lower() if artist else ""
        viable: list[tuple[tuple[int, float], dict]] = []
        n_blacklist = 0
        n_out_of_duration = 0
        n_total = 0
        for entry in entries:
            if not entry:
                continue
            n_total += 1
            entry_title = entry.get("title", "") or ""
            if BLACKLIST_KEYWORDS.search(entry_title):
                logger.debug("Skip (blacklist) : %s", entry_title)
                n_blacklist += 1
                continue
            entry_duration = entry.get("duration")
            if duration_ms is not None and entry_duration is not None:
                target_s = duration_ms / 1000.0
                tol = max(
                    DURATION_TOLERANCE_MS / 1000.0,
                    target_s * DURATION_TOLERANCE_PCT,
                )
                delta = abs(float(entry_duration) - target_s)
                if delta > tol:
                    logger.debug(
                        "Skip (durée %.1fs vs %.1fs cible, tol=%.1fs) : %s",
                        float(entry_duration), target_s, tol, entry_title,
                    )
                    n_out_of_duration += 1
                    continue
            else:
                delta = float("inf")
            channel = (entry.get("channel") or entry.get("uploader") or "").lower()
            if channel.endswith(" - topic") or channel == "topic":
                tier = 0
            elif "vevo" in channel or "official" in channel:
                tier = 1
            elif artist_primary and artist_primary in channel:
                tier = 2
            else:
                tier = 3
            viable.append(((tier, delta), entry))
        stats = {
            "n_total": n_total,
            "n_blacklist": n_blacklist,
            "n_out_of_duration": n_out_of_duration,
        }
        if not viable:
            return None, stats
        viable.sort(key=lambda x: x[0])
        best = viable[0][1]
        best_tier = viable[0][0][0]
        logger.debug(
            "Pick tier=%d channel=%s title=%s",
            best_tier,
            best.get("channel") or best.get("uploader"),
            best.get("title", "")[:60],
        )
        return best, stats

    @staticmethod
    def _classify_error(exc: Exception) -> AudioSourceError:
        msg = str(exc).lower()
        if "429" in msg or "too many requests" in msg or "rate" in msg:
            return AudioSourceRateLimited(str(exc))
        if (
            "available in your country" in msg
            or "geo" in msg
            or "blocked" in msg
            or "not available" in msg
        ):
            return AudioSourceError(f"Blocage géo : {exc}")
        return AudioSourceError(str(exc))


class _YTDLPLogger:
    """Forward yt-dlp messages vers le logger Python (au lieu de stdout)."""

    def debug(self, msg: str) -> None:
        logger.debug(msg)

    def info(self, msg: str) -> None:
        logger.debug(msg)

    def warning(self, msg: str) -> None:
        logger.warning(msg)

    def error(self, msg: str) -> None:
        logger.error(msg)
