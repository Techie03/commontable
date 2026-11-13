"""Order, order item, status event, and rating models."""

from sqlalchemy import Column, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.common import utc_datetime, utcnow

# Order statuses (contract section 2 state machine).
STATUS_PLACED = "PLACED"
STATUS_ACCEPTED = "ACCEPTED"
STATUS_PREPARING = "PREPARING"
STATUS_READY = "READY"
STATUS_ASSIGNED = "ASSIGNED"
STATUS_PICKED_UP = "PICKED_UP"
STATUS_DELIVERED = "DELIVERED"
STATUS_COMPLETED = "COMPLETED"
STATUS_REJECTED = "REJECTED"
STATUS_CANCELLED = "CANCELLED"
STATUS_REFUNDED = "REFUNDED"
STATUS_FAILED = "FAILED"

# States in which a customer/restaurant/admin may cancel the order.
CANCELLABLE_STATUSES = [STATUS_PLACED, STATUS_ACCEPTED, STATUS_PREPARING]

# Active orders shown on the dispatch board.
ACTIVE_STATUSES = [
    STATUS_PLACED,
    STATUS_ACCEPTED,
    STATUS_PREPARING,
    STATUS_READY,
    STATUS_ASSIGNED,
    STATUS_PICKED_UP,
]

TERMINAL_STATUSES = [
    STATUS_COMPLETED,
    STATUS_REJECTED,
    STATUS_CANCELLED,
    STATUS_REFUNDED,
    STATUS_FAILED,
]

# Fulfillment types allowed by the API in the slice (contract section 7).
# The column can hold saver/express later; the API rejects them now.
FULFILLMENT_PICKUP = "pickup"
FULFILLMENT_STANDARD = "standard"
SLICE_FULFILLMENT_TYPES = [FULFILLMENT_PICKUP, FULFILLMENT_STANDARD]

CHANNEL_APP = "app"
CHANNEL_DIRECT2DOOR = "direct2door"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String(20), unique=True, nullable=False, index=True)
    # Nullable: Direct2Door orders recorded by restaurant staff may name a
    # customer who has no CommonTable account (customer_name/phone instead).
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    restaurant_location_id = Column(Integer, ForeignKey("restaurant_locations.id"), nullable=True)
    channel = Column(String(20), nullable=False, default=CHANNEL_APP)
    fulfillment_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default=STATUS_PLACED, index=True)
    delivery_address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)
    promised_window_start = Column(utc_datetime, nullable=True)
    promised_window_end = Column(utc_datetime, nullable=True)
    prep_minutes = Column(Integer, nullable=True)

    # Money: integer cents. The checkout snapshot is written at placement
    # and never mutated afterwards (spec section 8.4).
    subtotal_cents = Column(Integer, nullable=False)
    delivery_fee_cents = Column(Integer, nullable=False)
    tax_cents = Column(Integer, nullable=False)
    tip_cents = Column(Integer, nullable=False, default=0)
    total_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    checkout_snapshot = Column(JSON, nullable=False)

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    placed_at = Column(utc_datetime, nullable=False, default=utcnow)
    accepted_at = Column(utc_datetime, nullable=True)
    ready_at = Column(utc_datetime, nullable=True)
    delivered_at = Column(utc_datetime, nullable=True)
    completed_at = Column(utc_datetime, nullable=True)
    cancelled_at = Column(utc_datetime, nullable=True)
    cancel_reason = Column(String(500), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)
    updated_at = Column(utc_datetime, nullable=False, default=utcnow, onupdate=utcnow)

    customer = relationship("Customer", back_populates="orders")
    restaurant = relationship("Restaurant", back_populates="orders")
    restaurant_location = relationship("RestaurantLocation")
    delivery_address = relationship("Address")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    events = relationship("StatusEvent", back_populates="order", cascade="all, delete-orphan")
    ledger_entries = relationship("LedgerEntry", back_populates="order")
    refunds = relationship("Refund", back_populates="order")
    delivery_tasks = relationship("DeliveryTask", back_populates="order")
    ratings = relationship("Rating", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    # RESTRICT on purpose: an item on any order cannot be deleted (contract).
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    name_snapshot = Column(String(255), nullable=False)
    price_snapshot_cents = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    modifiers_snapshot = Column(JSON, nullable=False, default=list)
    line_total_cents = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")


class StatusEvent(Base):
    """Append-only audit trail of every order transition (spec section 5)."""

    __tablename__ = "status_events"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(String(500), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    order = relationship("Order", back_populates="events")
    actor = relationship("User")


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=True)
    score = Column(Integer, nullable=False)  # 1-5
    comment = Column(String(1000), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    order = relationship("Order", back_populates="ratings")
