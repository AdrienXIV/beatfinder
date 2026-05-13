"""Génération PDF via Chromium headless — fidélité 100% à la vue web.

On bypasse weasyprint (lourd, dep Cairo/Pango) et reportlab (perte de fidélité)
en pilotant directement un Chromium-like installé sur la machine. C'est la même
binaire que celle utilisée pour la fenêtre `--app` de l'app desktop, donc en
contexte AppImage on a déjà la dépendance.

Le rendu est exactement celui de window.print() côté browser : @media print +
@page CSS appliqués, charts Chart.js rendus, fonts custom chargées.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

CHROMIUM_CANDIDATES = (
    "chromium-browser",
    "chromium",
    "google-chrome",
    "google-chrome-stable",
    "brave-browser",
    "microsoft-edge",
    "microsoft-edge-stable",
    "vivaldi",
)


def find_chromium_binary() -> str | None:
    """Retourne le chemin du premier Chromium-like trouvé dans PATH."""
    for cmd in CHROMIUM_CANDIDATES:
        path = shutil.which(cmd)
        if path:
            return path
    return None


def generate_pdf_from_url(
    url: str,
    output_path: Path,
    *,
    timeout: int = 60,
    virtual_time_budget_ms: int = 12000,
) -> Path:
    """Génère un PDF depuis l'URL via Chromium headless.

    Args:
        url: URL à imprimer. Doit être accessible par Chromium (typiquement
             http://127.0.0.1:PORT/...).
        output_path: chemin du PDF de sortie (sera créé/écrasé).
        timeout: timeout subprocess en secondes.
        virtual_time_budget_ms: durée virtuelle avancée par Chromium avant
             d'imprimer — permet aux JS async (Chart.js, etc.) de finir.

    Returns:
        Le path du PDF généré.

    Raises:
        RuntimeError: si aucun Chromium trouvé, exit non-zero, ou output absent.
    """
    binary = find_chromium_binary()
    if binary is None:
        raise RuntimeError(
            "Aucun navigateur Chromium-like trouvé pour générer le PDF "
            "(testé : chromium, google-chrome, brave, edge, vivaldi)."
        )

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    args = [
        binary,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--virtual-time-budget={virtual_time_budget_ms}",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={output_path}",
        "--no-pdf-header-footer",
        url,
    ]
    log.info("Generating PDF via %s for %s", Path(binary).name, url)
    result = subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[:1000]
        log.error("Chromium PDF failed (exit %d): %s", result.returncode, stderr)
        raise RuntimeError(
            f"Chromium headless a échoué (exit {result.returncode}). "
            f"stderr: {stderr[:200]}",
        )
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("PDF généré mais vide ou absent")
    size = output_path.stat().st_size
    log.info("PDF written: %s (%d KB)", output_path, size // 1024)
    return output_path
