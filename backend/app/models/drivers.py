"""Driver, vehicle, shift, and delivery task models."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.common import utc_datetime, utcnow

# Driver onboarding states (spec section 9).
ONBOARDING_APPLIED = "applied"
ONBOARDING_DOCUMENTS_PENDING = "documents_pending"
ONBOARDING_APPROVED = "approved"
ONBOARDING_REJECTED = "rejected"
ONBOARDING_SUSPENDED = "suspended"

# Delivery task states (spec section 9, plus "withdrawn" for dispatch
# overrides, which the contract's offer.withdrawn event describes).
TASK_OFFERED = "offered"
TASK_ACCEPTED = "accepted"
TASK_DECLINED = "declined"
TASK_WITHDRAWN = "withdrawn"
TASK_PICKED_UP = "picked_up"
TASK_DELIVERED = "delivered"
TASK_FAILED = "failed"


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    onboarding_status = Column(String(30), nullable=False, default=ONBOARDING_APPLIED)
    license_verified = Column(Boolean, nullable=False, default=False)
    online = Column(Boolean, nullable=False, default=False)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="driver_profile")
    vehicles = relationship("DriverVehicle", back_populates="driver", cascade="all, delete-orphan")
    shifts = relationship("DriverShift", back_populates="driver", cascade="all, delete-orphan")
    tasks = relationship("DeliveryTask", back_populates="driver")


class DriverVehicle(Base):
    __tablename__ = "driver_vehicles"

    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=True)
    make = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    year = Column(Integer, nullable=True)
    plate = Column(String(20), nullable=True)
    capacity = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    driver = relationship("Driver", back_populates="vehicles")


class DriverShift(Base):
    __tablename__ = "driver_shifts"

    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(utc_datetime, nullable=False, default=utcnow)
    ended_at = Column(utc_datetime, nullable=True)
    zone_id = Column(Integer, ForeignKey("service_zones.id"), nullable=True)

    driver = relationship("Driver", back_populates="shifts")


class DeliveryTask(Base):
    __tablename__ = "delivery_tasks"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    # No route_batch_id in the slice: no batching (contract section 7).
    status = Column(String(20), nullable=False, default=TASK_OFFERED, index=True)
    offered_pay_cents = Column(Integer, nullable=False)
    accepted_at = Column(utc_datetime, nullable=True)
    picked_up_at = Column(utc_datetime, nullable=True)
    delivered_at = Column(utc_datetime, nullable=True)
    proof_of_delivery_url = Column(String(1000), nullable=True)
    proof_note = Column(String(500), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)
    updated_at = Column(utc_datetime, nullable=False, default=utcnow, onupdate=utcnow)

    order = relationship("Order", back_populates="delivery_tasks")
    driver = relationship("Driver", back_populates="tasks")
