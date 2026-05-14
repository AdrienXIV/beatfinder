"""Vérification de nouvelles versions Beatfinder via GitHub Releases API.

Appel léger : `GET https://api.github.com/repos/AdrienXIV/beatfinder/releases/latest`
sans auth (rate-limit anonyme : 60 req/h par IP — largement suffisant pour
un check au démarrage). Timeout court (3s) pour ne pas bloquer le boot.

Sans réseau / GitHub down / rate-limited → retourne `update_available=False`
silencieusement (pas d'erreur affichée à l'utilisateur).
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from backend import __version__

log = logging.getLogger(__name__)

GITHUB_REPO = "AdrienXIV/beatfinder"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
TIMEOUT_SECONDS = 3.0


@dataclass(slots=True)
class UpdateCheck:
    current: str
    latest: str | None
    update_available: bool
    release_url: str | None
    release_notes: str | None
    published_at: str | None


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse 'v1.8.0' ou '1.8.0' → (1, 8, 0). Ignore les composants non-numériques."""
    cleaned = v.lstrip("vV").strip()
    parts: list[int] = []
    for p in cleaned.split("."):
        try:
            parts.append(int(p.split("-")[0]))  # ignore pre-release suffix ex: 1.8.0-rc1
        except ValueError:
            break
    return tuple(parts)


def check_for_update() -> UpdateCheck:
    """Compare la version courante à la dernière release GitHub.

    Returns: UpdateCheck (jamais None). Si pas de réseau ou GitHub indisponible,
    `latest=None` + `update_available=False`.
    """
    current = __version__
    try:
        req = urllib.request.Request(
            LATEST_RELEASE_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"beatfinder/{current}",
            },
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        log.debug("Update check failed (silent): %s", exc)
        return UpdateCheck(
            current=current,
            latest=None,
            update_available=False,
            release_url=None,
            release_notes=None,
            published_at=None,
        )

    latest_tag = (data.get("tag_name") or "").strip()
    latest_clean = latest_tag.lstrip("vV")
    release_url = data.get("html_url")
    release_notes = data.get("body")
    published_at = data.get("published_at")

    cur_parsed = _parse_version(current)
    latest_parsed = _parse_version(latest_tag) if latest_tag else ()
    update_available = bool(latest_parsed) and latest_parsed > cur_parsed

    return UpdateCheck(
        current=current,
        latest=latest_clean or None,
        update_available=update_available,
        release_url=release_url,
        release_notes=release_notes,
        published_at=published_at,
    )
