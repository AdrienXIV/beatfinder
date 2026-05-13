"""Entry point pour le packaging PyInstaller.

Délègue à `backend.main.main()` qui démarre uvicorn + sert le frontend.
"""
from __future__ import annotations

import sys


def _setup_pyinstaller_paths() -> None:
    """Quand on tourne depuis un binaire PyInstaller (`sys._MEIPASS`), ajoute
    le dossier extrait aux paths pour que les imports lazy fonctionnent."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and meipass not in sys.path:
        sys.path.insert(0, meipass)


if __name__ == "__main__":
    _setup_pyinstaller_paths()
    from backend.main import main
    main()
