"""Shared model helpers."""

from datetime import datetime, timezone

from sqlalchemy import DateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# UTC timestamps everywhere (spec section 9.3). SQLite stores them as naive
# ISO strings; Postgres stores timestamptz. Both read back as datetimes.
utc_datetime = DateTime(timezone=True)
