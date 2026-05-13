"""Tests du settings_store : load/save atomique des credentials Spotify."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.config import get_settings
from backend.infrastructure.settings_store import (
    SpotifyCreds,
    clear_spotify,
    load_settings,
    save_spotify,
    settings_path,
)


@pytest.fixture(autouse=True)
def _isolate_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Isolation totale : pas de `.env` (chdir tmpdir) + env Spotify clear.

    Sans le `chdir`, pydantic-settings lit le `.env` du cwd (le dev) et pollue
    les tests avec des credentials réels.
    """
    for var in (
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
        "SPOTIFY_REDIRECT_URI",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()


def test_load_settings_returns_defaults_when_file_absent(tmp_path: Path):
    s = load_settings(data_dir=tmp_path)
    assert s.spotify.client_id == ""
    assert s.spotify.client_secret == ""
    assert s.spotify.is_configured is False


def test_save_then_load_roundtrip(tmp_path: Path):
    creds = SpotifyCreds(
        client_id="my_id",
        client_secret="my_secret",
        redirect_uri="http://127.0.0.1:8888/callback",
    )
    saved = save_spotify(creds, data_dir=tmp_path)
    assert saved.spotify.client_id == "my_id"
    assert saved.spotify.is_configured is True

    loaded = load_settings(data_dir=tmp_path)
    assert loaded.spotify.client_id == "my_id"
    assert loaded.spotify.client_secret == "my_secret"


def test_save_is_atomic_via_temp_file(tmp_path: Path):
    # Pré-écrit un fichier corrompu, save_spotify doit l'écraser proprement
    bad = settings_path(tmp_path)
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("not json")

    save_spotify(SpotifyCreds(client_id="a", client_secret="b"), data_dir=tmp_path)
    # Pas de fichier .tmp laissé derrière
    assert not list(tmp_path.glob(".settings_*.tmp"))
    # Le fichier final est du JSON valide
    payload = json.loads(bad.read_text())
    assert payload["spotify"]["client_id"] == "a"


def test_clear_spotify_resets_creds(tmp_path: Path):
    save_spotify(SpotifyCreds(client_id="x", client_secret="y"), data_dir=tmp_path)
    cleared = clear_spotify(data_dir=tmp_path)
    assert cleared.spotify.client_id == ""
    assert cleared.spotify.client_secret == ""


def test_partial_save_preserves_other_fields(tmp_path: Path):
    # Save complet puis save partiel ne doit pas effacer les anciens champs
    save_spotify(
        SpotifyCreds(
            client_id="id1",
            client_secret="secret1",
            redirect_uri="http://localhost:9999/cb",
        ),
        data_dir=tmp_path,
    )
    # Save sans secret → garde l'ancien
    save_spotify(SpotifyCreds(client_id="id2", client_secret=""), data_dir=tmp_path)
    loaded = load_settings(data_dir=tmp_path)
    assert loaded.spotify.client_id == "id2"
    assert loaded.spotify.client_secret == "secret1"
    assert loaded.spotify.redirect_uri == "http://localhost:9999/cb"
