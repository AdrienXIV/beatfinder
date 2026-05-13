"""Routes FastAPI (sprint 3b + feature D + V1.7 actions/settings)."""
from __future__ import annotations

from backend.api import (
    routes_actions,
    routes_jobs,
    routes_playlists,
    routes_projects,
    routes_reports,
    routes_settings,
)

__all__ = [
    "routes_actions",
    "routes_jobs",
    "routes_playlists",
    "routes_projects",
    "routes_reports",
    "routes_settings",
]
