"""Sources de téléchargement audio (Strategy pattern)."""
from __future__ import annotations

from .base import (
    AudioSource,
    AudioSourceError,
    AudioSourceRateLimited,
    TrackNotFoundError,
)
from .youtube import YouTubeSource

__all__ = [
    "AudioSource",
    "AudioSourceError",
    "AudioSourceRateLimited",
    "TrackNotFoundError",
    "YouTubeSource",
]
