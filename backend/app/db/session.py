"""Database engine and session factory (PostgreSQL + PostGIS).

Models live in app/models/ (one module per entity group, per spec section 9).
Migrations are managed with Alembic (see backend/alembic/).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session, closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
