"""Database engine and session factory.

Production target is PostgreSQL + PostGIS. Tests override DATABASE_URL to
SQLite (see tests/conftest.py); the engine adapts its connect args for that.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

_connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    # SQLite needs this for use across FastAPI's threadpool / TestClient.
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url, pool_pre_ping=True, connect_args=_connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session, closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
