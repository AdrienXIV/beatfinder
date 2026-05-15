"""Entry point FastAPI + uvicorn launcher.

Démarrage dev (frontend séparé sur :5173) :
    uvicorn backend.main:app --reload --port 8000

Démarrage standalone prod (FastAPI sert /api + le static SvelteKit) :
    python -m backend.main

Mode binaire PyInstaller : dist/beatfinder/beatfinder (sert tout en standalone).

Auto-open browser au boot prod si frontend/build/ existe. Désactiver avec
BEATFINDER_NO_AUTO_OPEN=1.
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend import __version__
from backend.api import (
    routes_actions,
    routes_jobs,
    routes_playlists,
    routes_projects,
    routes_reports,
    routes_sessions,
    routes_settings,
)
from backend.api.jobs import JobQueue
from backend.api.schemas import HealthOut
from backend.config import IS_PACKAGED, get_settings
from backend.db import init_db, make_session_factory

log = logging.getLogger("backend.main")

DEV_CORS_ORIGINS: Final[list[str]] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
]


def _frontend_build_dir() -> Path:
    """En mode binaire, les data PyInstaller sont extraits dans sys._MEIPASS.
    En mode dev, on lit depuis le dossier source."""
    if IS_PACKAGED:
        meipass = Path(getattr(sys, "_MEIPASS", "."))
        return meipass / "frontend" / "build"
    return Path(__file__).resolve().parent.parent / "frontend" / "build"


FRONTEND_BUILD: Final[Path] = _frontend_build_dir()


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_dotenv()
    # `.env` peut influencer get_settings() — on bust le cache pour que le
    # premier accès post-dotenv lise les valeurs fraîchement chargées.
    get_settings.cache_clear()
    settings = get_settings()
    _setup_logging(settings.log_level)
    data_dir = settings.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = init_db()
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.data_dir = data_dir
    app.state.settings = settings
    app.state.job_queue = JobQueue()
    log.info("FastAPI ready — DATA_DIR=%s (packaged=%s)", data_dir, IS_PACKAGED)
    yield
    engine.dispose()
    log.info("FastAPI shutdown — engine disposed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Beatfinder API",
        version=__version__,
        description=(
            "Backend FastAPI pour Beatfinder — analyse playlists Spotify "
            "(rap/trap/house) et extraction de patterns audio."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(routes_playlists.router, prefix="/api")
    app.include_router(routes_reports.router, prefix="/api")
    app.include_router(routes_jobs.router, prefix="/api")
    app.include_router(routes_projects.router, prefix="/api")
    app.include_router(routes_actions.router, prefix="/api")
    app.include_router(routes_sessions.router, prefix="/api")
    app.include_router(routes_settings.router, prefix="/api")

    @app.get("/health", response_model=HealthOut, tags=["meta"])
    async def health() -> HealthOut:
        return HealthOut(
            status="ok",
            version=__version__,
            data_dir=str(app.state.data_dir),
        )

    # Frontend : un catch-all qui sert les fichiers du build/, fallback
    # index.html pour les routes SPA dynamiques (ex: /playlists/{id}).
    # Doit être défini APRÈS les routes API pour ne pas masquer /api/* et /health.
    if FRONTEND_BUILD.is_dir():
        index_html = FRONTEND_BUILD / "index.html"
        build_root = FRONTEND_BUILD.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str) -> FileResponse:
            # Préserver les 404 sur /api/* inconnu — sinon le SPA fallback
            # masquerait des bugs côté frontend.
            if full_path.startswith("api/"):
                raise HTTPException(
                    status_code=404, detail="API endpoint not found",
                )
            if full_path:
                try:
                    target = (FRONTEND_BUILD / full_path).resolve()
                    target.relative_to(build_root)
                except (ValueError, OSError):
                    return FileResponse(index_html)
                if target.is_file():
                    return FileResponse(target)
            return FileResponse(index_html)

        log.info("Frontend SPA served from %s", FRONTEND_BUILD)
    else:
        log.warning(
            "Frontend build not found at %s. "
            "Run `npm run build` in frontend/ then restart.",
            FRONTEND_BUILD,
        )

    return app


app = create_app()


def _find_app_window_browser() -> tuple[str, list[str]] | None:
    """Cherche un navigateur Chromium-like qui supporte le mode --app (vraie
    fenêtre sans chrome browser). Retourne (chemin, args) ou None.

    L'ordre privilégie Chromium → Chrome → Brave → Edge → Vivaldi.
    """
    import shutil
    import sys

    # Args partagés : profil isolé (n'interfère pas avec le Chrome perso de
    # l'utilisateur), WM_CLASS=Beatfinder pour que GNOME matche notre .desktop
    # et affiche l'icône Beatfinder dans la barre des tâches au lieu de Chrome.
    profile_dir = Path.home() / ".beatfinder" / ".browser-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    common_args = [
        "--app={url}",
        "--window-size=1280,900",
        f"--user-data-dir={profile_dir}",
        "--class=Beatfinder",
        "--name=Beatfinder",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    # macOS et Windows : Chrome/Brave/Edge ne sont pas dans $PATH, on doit
    # checker les chemins .app standards explicitement.
    if sys.platform == "darwin":
        home_apps = Path.home() / "Applications"
        path_candidates = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(home_apps / "Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            str(home_apps / "Brave Browser.app/Contents/MacOS/Brave Browser"),
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
        )
        for path in path_candidates:
            if Path(path).is_file():
                return path, common_args
    elif sys.platform == "win32":
        program_files = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
            Path(os.environ.get("LocalAppData", r"")) if os.environ.get("LocalAppData") else None,
        )
        path_subpaths = (
            r"Google\Chrome\Application\chrome.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe",
            r"Microsoft\Edge\Application\msedge.exe",
            r"Chromium\Application\chrome.exe",
        )
        for base in program_files:
            if base is None:
                continue
            for sub in path_subpaths:
                candidate = base / sub
                if candidate.is_file():
                    return str(candidate), common_args

    # Linux + fallback : chercher dans $PATH
    candidates = (
        "chromium-browser",
        "chromium",
        "google-chrome",
        "google-chrome-stable",
        "brave-browser",
        "microsoft-edge",
        "microsoft-edge-stable",
        "vivaldi",
    )
    for cmd in candidates:
        path = shutil.which(cmd)
        if path:
            return path, common_args
    return None


def _find_firefox_browser() -> tuple[str, list[str]] | None:
    """Fallback si aucun Chromium-like : Firefox avec --new-window pour avoir
    une fenêtre dédiée (au lieu d'un onglet dans la session perso). Retourne
    (chemin, args) ou None.

    Firefox n'a pas d'équivalent à --app, donc on accepte une fenêtre browser
    classique mais standalone.
    """
    import shutil
    import sys

    if sys.platform == "darwin":
        mac_paths = (
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            str(Path.home() / "Applications/Firefox.app/Contents/MacOS/firefox"),
        )
        for path in mac_paths:
            if Path(path).is_file():
                return path, ["--new-window", "{url}"]
    elif sys.platform == "win32":
        win_paths = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / r"Mozilla Firefox\firefox.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / r"Mozilla Firefox\firefox.exe",
        )
        for path in win_paths:
            if path.is_file():
                return str(path), ["--new-window", "{url}"]

    candidates = ("firefox", "firefox-esr")
    for cmd in candidates:
        path = shutil.which(cmd)
        if path:
            return path, ["--new-window", "{url}"]
    return None


def _open_browser_when_ready(host: str, port: int) -> None:
    """Attendre que /health réponde, puis ouvrir l'UI.

    Priorité :
    1. Chromium-like avec mode `--app=URL` → vraie fenêtre standalone "app native"
       + watchdog qui kill uvicorn quand la fenêtre se ferme.
    2. Firefox avec `--new-window` → fenêtre dédiée (pas d'onglet dans la session
       perso), mais pas de watchdog (Firefox détache son process).
    3. `webbrowser.open()` → onglet dans le browser par défaut (fallback ultime).
    """
    import http.client
    import subprocess
    import sys
    import threading
    import time
    import webbrowser

    chromium = _find_app_window_browser()
    firefox = _find_firefox_browser() if chromium is None else None
    profile_dir = Path.home() / ".beatfinder" / ".browser-profile"

    def _watchdog_chrome_mac() -> None:
        """Sur macOS, le binaire Chrome se détache de son parent (XPC vers
        l'instance principale) → proc.wait() retourne tout de suite. On
        surveille via pgrep si un process Chrome utilise notre profile-dir.
        Quand plus aucun → la fenêtre Beatfinder est fermée → shutdown.
        """
        marker = str(profile_dir)
        # Petit grace period le temps que Chrome démarre son process.
        time.sleep(3)
        while True:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", marker],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if result.returncode != 0:
                    log.info("Browser window closed (no chrome process) → shutting down server")
                    os._exit(0)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)

    def worker() -> None:
        url = f"http://{host}:{port}/"
        for _ in range(40):  # ~10s max
            try:
                conn = http.client.HTTPConnection(host, port, timeout=0.5)
                conn.request("GET", "/health")
                resp = conn.getresponse()
                if resp.status == 200:
                    if chromium is not None:
                        cmd, args_tpl = chromium
                        args = [cmd] + [a.format(url=url) for a in args_tpl]
                        log.info("Opening app window via %s (--app mode)", cmd)
                        try:
                            proc = subprocess.Popen(
                                args,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=True,
                            )
                            if sys.platform == "darwin":
                                # macOS : proc.wait() inutile (Chrome se détache).
                                # On surveille via pgrep le profile-dir.
                                _watchdog_chrome_mac()
                            else:
                                # Linux/Windows : proc.wait() bloque jusqu'à la
                                # fermeture de la fenêtre (Chrome reste attaché).
                                proc.wait()
                                log.info("Browser window closed → shutting down server")
                                os._exit(0)
                        except OSError as exc:
                            log.warning("Chromium --app failed: %s — fallback Firefox/webbrowser", exc)
                    if firefox is not None:
                        cmd, args_tpl = firefox
                        args = [cmd] + [a.format(url=url) for a in args_tpl]
                        log.info("Opening dedicated window via %s (--new-window)", cmd)
                        try:
                            subprocess.Popen(
                                args,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=True,
                            )
                            # Pas de watchdog : Firefox détache son process et
                            # ne reflète pas la fermeture de fenêtre. L'utilisateur
                            # devra Ctrl-C dans le terminal pour arrêter uvicorn.
                            return
                        except OSError as exc:
                            log.warning("Firefox --new-window failed: %s — fallback webbrowser", exc)
                    log.info("Falling back to webbrowser.open() (browser default)")
                    webbrowser.open(url)
                    return
            except OSError:
                pass
            finally:
                try:
                    conn.close()  # type: ignore[name-defined]
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0.25)
        log.warning("Auto-open: server not ready after 10s, skipping browser launch")

    threading.Thread(target=worker, daemon=True).start()


def _is_port_in_use(host: str, port: int) -> bool:
    """Test si un service tourne déjà sur (host, port). Évite de relancer
    une instance Beatfinder quand l'utilisateur clique sur l'icône dock
    macOS (qui re-exécute le binaire .app)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        try:
            sock.connect((host, port))
            return True
        except (OSError, TimeoutError):
            return False


def _focus_existing_window(host: str, port: int) -> None:
    """Focus la fenêtre Beatfinder existante (cas reopen via dock macOS).

    Sur macOS, clic sur l'icône dock d'une app déjà lancée re-exécute le
    binaire. La fenêtre Beatfinder tourne dans une instance Chrome séparée
    (via `--user-data-dir=~/.beatfinder/.browser-profile`). On NE PEUT PAS
    utiliser `tell application "Google Chrome" to activate` : ça cible le
    Chrome perso de l'utilisateur (instance principale), qui spawne sa page
    d'accueil (Google) si pas déjà ouvert — la fenêtre Beatfinder reste
    derrière.

    Solution : retrouver le PID du process Chrome qui tourne avec notre
    profile-dir via `pgrep -f`, puis activer ce process précis via
    `System Events`. Robuste, ne touche pas au Chrome perso.

    Sur Linux/Windows : pas d'équivalent simple — on log et on exit.
    """
    import subprocess
    import sys

    if sys.platform != "darwin":
        log.info("Already running on %s:%d, exiting", host, port)
        return

    profile_dir = str(Path.home() / ".beatfinder" / ".browser-profile")

    try:
        result = subprocess.run(
            ["pgrep", "-f", profile_dir],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        pids = [p for p in result.stdout.strip().split("\n") if p.isdigit()]
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("pgrep failed while looking for Beatfinder Chrome: %s", exc)
        return

    if not pids:
        log.warning(
            "No Chrome process found for profile-dir %s — uvicorn tourne mais "
            "la fenêtre app a été fermée. Rien à focus.",
            profile_dir,
        )
        return

    # On prend le premier PID — c'est le process Chrome racine de notre
    # instance (les Helpers et Renderers descendent de lui mais on n'en a
    # pas besoin pour System Events).
    pid = pids[0]
    script = (
        'tell application "System Events" to '
        f"set frontmost of (first process whose unix id is {pid}) to true"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
        )
        log.info("Focused existing Beatfinder Chrome process (PID %s)", pid)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("Could not focus existing window: %s", exc)


def main() -> None:
    """Standalone launcher pour packaging desktop."""
    import uvicorn

    load_dotenv()
    get_settings.cache_clear()
    settings = get_settings()

    # Single-instance guard : si une instance Beatfinder tourne déjà sur
    # ce port (cas typique macOS : clic dock icon re-exécute le binaire),
    # on focus la fenêtre existante et on exit. Évite "Chrome ouvre Google
    # parce que --app=URL est refusé pour duplicate user-data-dir".
    if _is_port_in_use(settings.beatfinder_host, settings.beatfinder_port):
        log.info(
            "Beatfinder instance already running on %s:%d — focusing existing window",
            settings.beatfinder_host, settings.beatfinder_port,
        )
        _focus_existing_window(settings.beatfinder_host, settings.beatfinder_port)
        return

    if FRONTEND_BUILD.is_dir() and not settings.beatfinder_no_auto_open:
        _open_browser_when_ready(settings.beatfinder_host, settings.beatfinder_port)

    uvicorn.run(
        app,
        host=settings.beatfinder_host,
        port=settings.beatfinder_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
