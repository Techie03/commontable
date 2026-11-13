"""Notification, integration, and support ticket models."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.common import utc_datetime, utcnow

# Notification types (contract section 3).
NOTIF_ORDER_ACCEPTED = "order_accepted"
NOTIF_ORDER_PREPARING = "order_preparing"
NOTIF_DRIVER_ASSIGNED = "driver_assigned"
NOTIF_ORDER_PICKED_UP = "order_picked_up"
NOTIF_ORDER_DELIVERED = "order_delivered"
NOTIF_ORDER_PLACED = "order_placed"
NOTIF_ORDER_CANCELLED = "order_cancelled"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(String(1000), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="notifications")


class Integration(Base):
    """Direct2Door integrations (dashboard handoff only in the slice)."""

    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # api | webhook | widget | dashboard_handoff | pos_adapter
    provider = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    # External secrets-manager reference only; never a stored secret.
    credentials_ref = Column(String(255), nullable=True)
    authorized_at = Column(utc_datetime, nullable=True)
    authorized_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    reporter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False, default="other")
    status = Column(String(20), nullable=False, default="open")
    description = Column(String(2000), nullable=False)
    resolution = Column(String(2000), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)
    resolved_at = Column(utc_datetime, nullable=True)
