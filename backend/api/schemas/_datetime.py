"""Type Pydantic pour datetime sérialisé en UTC ISO 8601 avec suffixe 'Z'.

Pourquoi : SQLite/SQLAlchemy stocke les `datetime.now(UTC)` comme strings naïves
sans tzinfo. À la sérialisation Pydantic par défaut, l'ISO ressort sans suffixe
de timezone → côté frontend, `new Date(iso)` les interprète comme heure locale
et affiche un décalage (2h en France l'été). Forcer l'émission avec 'Z' garantit
que tous les clients (JS, mobile, etc.) parsent comme UTC.

Usage :
    from datetime import datetime
    from ._datetime import UtcDatetime

    class Foo(BaseModel):
        created_at: UtcDatetime          # required
        deleted_at: UtcDatetime | None   # optional
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer


def _to_utc_iso_z(dt: datetime | None) -> str | None:
    """Sérialise un datetime en ISO 8601 UTC avec suffixe 'Z' explicite.

    Datetimes naïfs (sans tzinfo) sont assumés en UTC — c'est notre convention
    interne (cf. `_now_utc` dans `backend/domain/models.py`).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    # isoformat retourne `2026-05-16T14:32:00+00:00` → on remplace par 'Z'
    # qui est l'écriture canonique reconnue par tous les parseurs JS/JSON.
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[
    datetime,
    PlainSerializer(_to_utc_iso_z, return_type=str, when_used="json"),
]
