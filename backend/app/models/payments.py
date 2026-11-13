"""Payments, ledger, refunds, settlements, pricing rules, idempotency keys."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.common import utc_datetime, utcnow

# Ledger entry types (contract section 6).
ENTRY_CUSTOMER_CHARGE = "customer_charge"
ENTRY_DELIVERY_COST_EXPENSE = "delivery_cost_expense"
ENTRY_RESTAURANT_PAYABLE = "restaurant_payable"
ENTRY_DELIVERY_FEE_REVENUE = "delivery_fee_revenue"
ENTRY_PLATFORM_FEE_REVENUE = "platform_fee_revenue"
ENTRY_DRIVER_PAYABLE = "driver_payable"
ENTRY_REFUND = "refund"
ENTRY_ADJUSTMENT = "adjustment"

DIRECTION_DEBIT = "debit"
DIRECTION_CREDIT = "credit"

# Pricing rule keys (contract section 5). Values live in pricing_rules and
# are read by the pricing service; business logic never hardcodes them.
RULE_STANDARD_DELIVERY_FEE = "standard_delivery_fee_cents"
RULE_PICKUP_DELIVERY_FEE = "pickup_delivery_fee_cents"
RULE_DRIVER_BASE_PAY = "driver_base_pay_cents"
RULE_RESTAURANT_FULFILLMENT_FEE = "restaurant_fulfillment_fee_cents"

ALL_RULE_KEYS = [
    RULE_STANDARD_DELIVERY_FEE,
    RULE_PICKUP_DELIVERY_FEE,
    RULE_DRIVER_BASE_PAY,
    RULE_RESTAURANT_FULFILLMENT_FEE,
]


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # "stub" in the slice
    provider_payment_id = Column(String(255), nullable=True)
    provider_status = Column(String(50), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    # Food payment model: platform-processed in the slice (contract section 6).
    food_processor = Column(String(20), nullable=False, default="platform")
    created_at = Column(utc_datetime, nullable=False, default=utcnow)


class LedgerEntry(Base):
    """Append-only. Balances are derived, never mutated."""

    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    entry_type = Column(String(50), nullable=False)
    direction = Column(String(10), nullable=False)  # debit | credit
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    description = Column(String(500), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    order = relationship("Order", back_populates="ledger_entries")


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    amount_cents = Column(Integer, nullable=False)
    reason = Column(String(500), nullable=True)
    issued_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), nullable=False, default="issued")
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    order = relationship("Order", back_populates="refunds")


class Settlement(Base):
    """Settlement summary records (computed from the ledger; no money moves)."""

    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    period_start = Column(utc_datetime, nullable=True)
    period_end = Column(utc_datetime, nullable=True)
    total_payable_cents = Column(Integer, nullable=False, default=0)
    total_fees_cents = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(utc_datetime, nullable=False, default=utcnow)


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True)
    service_zone_id = Column(Integer, ForeignKey("service_zones.id"), nullable=True, index=True)
    rule_key = Column(String(100), nullable=False, index=True)
    value_cents = Column(Integer, nullable=False)
    fulfillment_type = Column(String(20), nullable=True)
    active_from = Column(utc_datetime, nullable=True)
    active_to = Column(utc_datetime, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    zone = relationship("ServiceZone", back_populates="pricing_rules")


class IdempotencyKey(Base):
    """One row per (key, user) for POST /orders; retries return the original."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("key", "user_id", name="uq_idempotency_key_user"),
    )

    id = Column(Integer, primary_key=True)
    key = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    request_hash = Column(String(64), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)
