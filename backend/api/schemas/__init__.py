"""Pydantic schemas pour les routes API.

Split par domaine pour rester maintenable. Re-export pour préserver
l'import historique `from backend.api.schemas import ...`.
"""
from __future__ import annotations

from .actions import (
    ActionItemOut,
    ActionPlanOut,
    ComparedSourceOut,
    ComparedTargetOut,
    StylePredictionItemOut,
    StylePredictionOut,
    ThresholdPresetOut,
)
from .core import (
    AppStatusOut,
    CacheCategoryOut,
    CacheFlushOut,
    CacheStatsOut,
    DBCountsOut,
    HealthOut,
    SpotifySettingsIn,
    SpotifySettingsOut,
    UpdateCheckOut,
)
from .jobs import AnalyzeRequest, AnalyzeTrackRequest, JobOut, JobProgressOut
from .playlists import (
    PatternOut,
    PatternSummaryOut,
    PlaylistDetailOut,
    PlaylistSummaryOut,
    TrackAnalysisOut,
    TrackOut,
)
from .reports import (
    BriefOut,
    CompareOut,
    CompareRequest,
    MultiCompareOut,
    MultiCompareSourceOut,
    MultiStatRowOut,
    SpectralRadarOut,
)
from .overrides import TrackOverrideIn, TrackOverrideOut
from .sessions import (
    CreateSessionIn,
    CreativeSessionDetailOut,
    CreativeSessionSummaryOut,
    SessionVersionOut,
)

__all__ = [
    "ActionItemOut",
    "ActionPlanOut",
    "AnalyzeRequest",
    "AnalyzeTrackRequest",
    "AppStatusOut",
    "BriefOut",
    "CacheCategoryOut",
    "CacheFlushOut",
    "CacheStatsOut",
    "CompareOut",
    "CompareRequest",
    "ComparedSourceOut",
    "ComparedTargetOut",
    "CreateSessionIn",
    "CreativeSessionDetailOut",
    "CreativeSessionSummaryOut",
    "DBCountsOut",
    "HealthOut",
    "JobOut",
    "JobProgressOut",
    "MultiCompareOut",
    "MultiCompareSourceOut",
    "MultiStatRowOut",
    "PatternOut",
    "PatternSummaryOut",
    "PlaylistDetailOut",
    "PlaylistSummaryOut",
    "SessionVersionOut",
    "SpectralRadarOut",
    "SpotifySettingsIn",
    "SpotifySettingsOut",
    "TrackOverrideIn",
    "TrackOverrideOut",
    "UpdateCheckOut",
    "StylePredictionItemOut",
    "StylePredictionOut",
    "ThresholdPresetOut",
    "TrackAnalysisOut",
    "TrackOut",
]
