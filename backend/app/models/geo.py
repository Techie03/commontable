"""Geography models: service zones and addresses."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.types import GeometryOrText
from app.models.common import utc_datetime, utcnow


class ServiceZone(Base):
    __tablename__ = "service_zones"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    # PostGIS polygon on Postgres, WKT text on SQLite (see db/types.py).
    boundary = Column(GeometryOrText("POLYGON", srid=4326), nullable=True)
    # Primary serviceability check in the slice: postal-code list.
    postal_codes = Column(JSON, nullable=False, default=list)
    tax_rate_bps = Column(Integer, nullable=False, default=825)
    hours_json = Column(JSON, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    pricing_rules = relationship("PricingRule", back_populates="zone")


class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    line1 = Column(String(255), nullable=False)
    line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    postal_code = Column(String(20), nullable=False, index=True)
    # PostGIS point on Postgres, WKT text on SQLite.
    location = Column(GeometryOrText("POINT", srid=4326), nullable=True)
    label = Column(String(100), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    def formatted(self) -> str:
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        return ", ".join(parts)
