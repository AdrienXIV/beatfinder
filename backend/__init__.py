"""Beatfinder backend — analyse de patterns audio pour beatmakers.

Expose `__version__` résolu dans l'ordre :
  1. `importlib.metadata.version("beatfinder")` — si le package est installé
     via `pip install -e .` ou une release.
  2. `pyproject.toml` embarqué dans le bundle PyInstaller (`sys._MEIPASS`).
  3. `pyproject.toml` à la racine du repo (mode dev source pur).
  4. fallback "0.0.0".

Source unique de vérité : la clé `[project].version` du `pyproject.toml`.
"""
from __future__ import annotations

import sys
import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path


def _read_pyproject_version(py_path: Path) -> str | None:
    if not py_path.is_file():
        return None
    try:
        with py_path.open("rb") as f:
            data = tomllib.load(f)
        v = data.get("project", {}).get("version")
        return v if isinstance(v, str) else None
    except (OSError, tomllib.TOMLDecodeError):
        return None


def _resolve_version() -> str:
    try:
        return _pkg_version("beatfinder")
    except PackageNotFoundError:
        pass

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        v = _read_pyproject_version(Path(meipass) / "pyproject.toml")
        if v:
            return v

    v = _read_pyproject_version(
        Path(__file__).resolve().parent.parent / "pyproject.toml"
    )
    if v:
        return v

    return "0.0.0"


__version__ = _resolve_version()

__all__ = ["__version__"]
