"""Beatfinder backend — analyse de patterns audio pour beatmakers.

Expose `__version__` lu depuis le `pyproject.toml` quand le package est
installé (`pip install -e .`), fallback hardcodé sinon (mode source pur).
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("beatfinder")
except PackageNotFoundError:
    __version__ = "1.7.0"

__all__ = ["__version__"]
