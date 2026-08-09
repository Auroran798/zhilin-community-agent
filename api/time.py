"""UTC helpers used by all business services.

The project used naive ``datetime.utcnow`` values before Stage 7.  New writes
are timezone-aware UTC; ``as_utc`` deliberately accepts legacy SQLite values
so a migrated demo database remains readable during the transition.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
