"""Pricing service: reads pricing_rules, never hardcodes values.

Tax comes from the zone (tax_rate_bps) and is computed on the food subtotal
only. Total = subtotal + delivery fee + tax + tip (contract section 5).
"""

from sqlalchemy.orm import Session

from app.core.errors import bad_request
from app.models.geo import ServiceZone
from app.models.orders import FULFILLMENT_PICKUP, FULFILLMENT_STANDARD
from app.models.payments import (
    RULE_DRIVER_BASE_PAY,
    RULE_PICKUP_DELIVERY_FEE,
    RULE_RESTAURANT_FULFILLMENT_FEE,
    RULE_STANDARD_DELIVERY_FEE,
    PricingRule,
)


def get_rule_value(db: Session, zone_id: int | None, rule_key: str) -> int:
    """Look up a pricing rule for a zone, falling back to a global rule."""
    rule = (
        db.query(PricingRule)
        .filter(
            PricingRule.rule_key == rule_key,
            PricingRule.service_zone_id == zone_id,
            PricingRule.active.is_(True),
        )
        .first()
    )
    if rule is None:
        rule = (
            db.query(PricingRule)
            .filter(
                PricingRule.rule_key == rule_key,
                PricingRule.service_zone_id.is_(None),
                PricingRule.active.is_(True),
            )
            .first()
        )
    if rule is None:
        raise bad_request(
            f"Pricing is not configured for this zone ({rule_key})",
            code="pricing_not_configured",
        )
    return rule.value_cents


def compute_tax_cents(subtotal_cents: int, tax_rate_bps: int) -> int:
    """Tax on the food subtotal only, rounded to the nearest cent."""
    return (subtotal_cents * tax_rate_bps + 5000) // 10000


def quote_checkout(
    db: Session,
    zone: ServiceZone,
    fulfillment_type: str,
    subtotal_cents: int,
    tip_cents: int = 0,
) -> dict:
    """Full fee breakdown for a checkout. All values come from pricing_rules
    and the zone; nothing here is hardcoded."""
    if fulfillment_type == FULFILLMENT_PICKUP:
        fee_key = RULE_PICKUP_DELIVERY_FEE
    elif fulfillment_type == FULFILLMENT_STANDARD:
        fee_key = RULE_STANDARD_DELIVERY_FEE
    else:
        raise bad_request(
            f"Fulfillment type '{fulfillment_type}' is not offered in this slice",
            code="fulfillment_not_supported",
        )
    delivery_fee_cents = get_rule_value(db, zone.id, fee_key)
    tax_cents = compute_tax_cents(subtotal_cents, zone.tax_rate_bps)
    total_cents = subtotal_cents + delivery_fee_cents + tax_cents + tip_cents
    return {
        "subtotal_cents": subtotal_cents,
        "delivery_fee_cents": delivery_fee_cents,
        "tax_cents": tax_cents,
        "tip_cents": tip_cents,
        "total_cents": total_cents,
        "tax_rate_bps": zone.tax_rate_bps,
        "currency": "USD",
    }


def driver_pay_cents(db: Session, zone_id: int | None) -> int:
    """Base driver pay per delivery, from pricing rules."""
    return get_rule_value(db, zone_id, RULE_DRIVER_BASE_PAY)


def fulfillment_fee_cents(db: Session, zone_id: int | None) -> int:
    """Restaurant fulfillment fee per delivery order, from pricing rules."""
    return get_rule_value(db, zone_id, RULE_RESTAURANT_FULFILLMENT_FEE)
