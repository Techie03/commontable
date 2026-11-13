"""Order service: placement, checkout snapshot, and the state machine.

State machine (contract section 2):
  PLACED -> ACCEPTED -> PREPARING -> READY -> ASSIGNED -> PICKED_UP
  -> DELIVERED -> COMPLETED
Pickup: PLACED -> ACCEPTED -> PREPARING -> READY -> COMPLETED.
Terminal side states: REJECTED, CANCELLED, REFUNDED, FAILED.

Every transition writes a status_events row. The checkout snapshot is
written at placement and never mutated afterwards.
"""

import hashlib
import json

from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, not_found
from app.models.geo import Address, ServiceZone
from app.models.identity import User
from app.models.orders import (
    CANCELLABLE_STATUSES,
    CHANNEL_DIRECT2DOOR,
    FULFILLMENT_PICKUP,
    SLICE_FULFILLMENT_TYPES,
    STATUS_ACCEPTED,
    STATUS_ASSIGNED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PICKED_UP,
    STATUS_PLACED,
    STATUS_PREPARING,
    STATUS_READY,
    STATUS_REFUNDED,
    STATUS_REJECTED,
    Order,
    OrderItem,
    StatusEvent,
)
from app.models.payments import IdempotencyKey
from app.models.restaurants import MenuItem, Modifier, Restaurant, RestaurantLocation
from app.services import ledger as ledger_service
from app.services import notifications
from app.services import pricing as pricing_service

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    STATUS_PLACED: [STATUS_ACCEPTED, STATUS_REJECTED, STATUS_CANCELLED, STATUS_REFUNDED],
    STATUS_ACCEPTED: [STATUS_PREPARING, STATUS_CANCELLED, STATUS_REFUNDED],
    STATUS_PREPARING: [STATUS_READY, STATUS_CANCELLED, STATUS_REFUNDED],
    STATUS_READY: [STATUS_ASSIGNED, STATUS_COMPLETED, STATUS_REFUNDED],  # COMPLETED: pickup only
    STATUS_ASSIGNED: [STATUS_READY, STATUS_PICKED_UP, STATUS_REFUNDED],  # READY: driver declined
    STATUS_PICKED_UP: [STATUS_DELIVERED, STATUS_FAILED, STATUS_REFUNDED],
    STATUS_DELIVERED: [STATUS_COMPLETED, STATUS_REFUNDED],
    STATUS_COMPLETED: [STATUS_REFUNDED],
    STATUS_CANCELLED: [],
    STATUS_REJECTED: [],
    STATUS_REFUNDED: [],
    STATUS_FAILED: [],
}


def record_transition(
    db: Session,
    order: Order,
    to_status: str,
    actor: User | None = None,
    reason: str | None = None,
) -> StatusEvent:
    """Move an order to a new status, enforcing the state machine and
    writing the audit row. Raises 400 on an illegal transition."""
    allowed = ALLOWED_TRANSITIONS.get(order.status, [])
    if to_status not in allowed:
        raise bad_request(
            f"Order cannot move from {order.status} to {to_status}",
            code="invalid_transition",
        )
    from_status = order.status
    order.status = to_status
    event = StatusEvent(
        order_id=order.id,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor.id if actor else None,
        reason=reason,
    )
    db.add(event)
    return event


def find_zone_for_postal_code(db: Session, postal_code: str) -> ServiceZone | None:
    """Primary serviceability check: the zone postal-code list."""
    zones = db.query(ServiceZone).filter(ServiceZone.active.is_(True)).all()
    for zone in zones:
        if postal_code in (zone.postal_codes or []):
            return zone
    return None


def _modifier_map(db: Session, item_ids: list[int]) -> dict[int, Modifier]:
    modifiers = db.query(Modifier).filter(Modifier.menu_item_id.in_(item_ids)).all()
    return {m.id: m for m in modifiers}


def place_order(
    db: Session,
    *,
    user: User,
    restaurant_id: int,
    items: list[dict],
    fulfillment_type: str,
    delivery_address: dict | None,
    tip_cents: int = 0,
    channel: str = "app",
    customer_name: str | None = None,
    customer_phone: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[Order, bool]:
    """Place an order. Returns (order, created). A retried request with the
    same Idempotency-Key + same user returns the original order."""
    if idempotency_key:
        existing = (
            db.query(IdempotencyKey)
            .filter(
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.user_id == user.id,
            )
            .first()
        )
        if existing is not None and existing.order_id is not None:
            original = db.query(Order).filter(Order.id == existing.order_id).first()
            if original is not None:
                return original, False

    if fulfillment_type not in SLICE_FULFILLMENT_TYPES:
        raise bad_request(
            f"Fulfillment type '{fulfillment_type}' is not offered yet. "
            "Pickup and Standard are available.",
            code="fulfillment_not_supported",
        )
    if tip_cents < 0:
        raise bad_request("Tip cannot be negative")

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None or restaurant.status not in ("active", "demo"):
        raise not_found("Restaurant not found or not orderable")

    if not items:
        raise bad_request("An order needs at least one item")

    # Resolve the delivery zone. Pickup orders use the restaurant's zone.
    location = (
        db.query(RestaurantLocation)
        .filter(RestaurantLocation.restaurant_id == restaurant.id)
        .first()
    )
    zone: ServiceZone | None = None
    address_row: Address | None = None
    if fulfillment_type == FULFILLMENT_PICKUP:
        if location and location.service_zone_ids:
            zone = db.query(ServiceZone).filter(
                ServiceZone.id == location.service_zone_ids[0]
            ).first()
        if zone is None:
            zone = db.query(ServiceZone).filter(ServiceZone.active.is_(True)).first()
        if zone is None:
            raise bad_request("No active service zone is configured",
                             code="zone_not_configured")
    else:
        if not delivery_address:
            raise bad_request("A delivery address is required for Standard delivery")
        zone = find_zone_for_postal_code(db, delivery_address["postal_code"])
        if zone is None:
            raise bad_request(
                "Delivery is not available at that postal code yet",
                code="not_serviceable",
            )
        if location and location.service_zone_ids and zone.id not in location.service_zone_ids:
            raise bad_request(
                "That restaurant does not deliver to your address",
                code="not_serviceable",
            )
        address_row = Address(
            user_id=user.id if channel != CHANNEL_DIRECT2DOOR else None,
            line1=delivery_address["line1"],
            line2=delivery_address.get("line2"),
            city=delivery_address["city"],
            state=delivery_address["state"],
            postal_code=delivery_address["postal_code"],
        )
        db.add(address_row)
        db.flush()

    # Validate items against the restaurant's menu; snapshot prices now.
    item_ids = [it["menu_item_id"] for it in items]
    menu_items = (
        db.query(MenuItem)
        .join(MenuItem.menu)
        .filter(MenuItem.id.in_(item_ids))
        .all()
    )
    by_id = {mi.id: mi for mi in menu_items}
    modifiers = _modifier_map(db, item_ids)
    snapshot_items: list[dict] = []
    subtotal_cents = 0
    for it in items:
        menu_item = by_id.get(it["menu_item_id"])
        if menu_item is None or menu_item.menu.restaurant_id != restaurant.id:
            raise bad_request(
                f"Menu item {it['menu_item_id']} does not belong to this restaurant"
            )
        if not menu_item.available:
            raise bad_request(f"'{menu_item.name}' is not available right now")
        quantity = it.get("quantity", 1)
        if quantity < 1:
            raise bad_request("Item quantity must be at least 1")
        modifier_snaps: list[dict] = []
        modifier_total = 0
        for mod in it.get("modifiers") or []:
            mod_id = mod["modifier_id"] if isinstance(mod, dict) else mod
            modifier = modifiers.get(mod_id)
            if modifier is None or modifier.menu_item_id != menu_item.id:
                raise bad_request(f"Modifier {mod_id} does not belong to this item")
            modifier_snaps.append(
                {
                    "modifier_id": modifier.id,
                    "name": modifier.name,
                    "price_delta_cents": modifier.price_delta_cents,
                }
            )
            modifier_total += modifier.price_delta_cents
        line_total = (menu_item.price_cents + modifier_total) * quantity
        subtotal_cents += line_total
        snapshot_items.append(
            {
                "menu_item_id": menu_item.id,
                "name": menu_item.name,
                "price_cents": menu_item.price_cents,
                "quantity": quantity,
                "modifiers": modifier_snaps,
                "line_total_cents": line_total,
            }
        )

    quote = pricing_service.quote_checkout(
        db, zone, fulfillment_type, subtotal_cents, tip_cents
    )

    # Customer link: app orders belong to the caller's customer profile;
    # Direct2Door orders name a customer without an account.
    customer = None
    if channel != CHANNEL_DIRECT2DOOR:
        customer = user.customer_profile
        if customer is None:
            from app.models.identity import Customer

            customer = Customer(user_id=user.id)
            db.add(customer)
            db.flush()

    order = Order(
        order_number="CT-TEMP",
        customer_id=customer.id if customer else None,
        customer_name=customer_name,
        customer_phone=customer_phone,
        restaurant_id=restaurant.id,
        restaurant_location_id=location.id if location else None,
        channel=channel,
        fulfillment_type=fulfillment_type,
        status=STATUS_PLACED,
        delivery_address_id=address_row.id if address_row else None,
        subtotal_cents=quote["subtotal_cents"],
        delivery_fee_cents=quote["delivery_fee_cents"],
        tax_cents=quote["tax_cents"],
        tip_cents=quote["tip_cents"],
        total_cents=quote["total_cents"],
        currency="USD",
        checkout_snapshot={
            "restaurant_id": restaurant.id,
            "restaurant_name": restaurant.name,
            "fulfillment_type": fulfillment_type,
            "channel": channel,
            "zone_id": zone.id,
            "zone_name": zone.name,
            "items": snapshot_items,
            "subtotal_cents": quote["subtotal_cents"],
            "delivery_fee_cents": quote["delivery_fee_cents"],
            "tax_cents": quote["tax_cents"],
            "tax_rate_bps": quote["tax_rate_bps"],
            "tip_cents": quote["tip_cents"],
            "total_cents": quote["total_cents"],
            "currency": "USD",
        },
    )
    db.add(order)
    db.flush()
    order.order_number = f"CT-{order.id:06d}"

    for snap in snapshot_items:
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=snap["menu_item_id"],
                name_snapshot=snap["name"],
                price_snapshot_cents=snap["price_cents"],
                quantity=snap["quantity"],
                modifiers_snapshot=snap["modifiers"],
                line_total_cents=snap["line_total_cents"],
            )
        )
    db.add(
        StatusEvent(
            order_id=order.id,
            from_status=None,
            to_status=STATUS_PLACED,
            actor_user_id=user.id,
        )
    )

    # Ledger entries for the order (contract section 6).
    driver_pay = pricing_service.driver_pay_cents(db, zone.id)
    fulfillment_fee = pricing_service.fulfillment_fee_cents(db, zone.id)
    ledger_service.write_order_entries(db, order, driver_pay, fulfillment_fee)

    if idempotency_key:
        request_hash = hashlib.sha256(
            json.dumps(
                {"restaurant_id": restaurant_id, "items": items,
                 "fulfillment_type": fulfillment_type},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        db.add(
            IdempotencyKey(
                key=idempotency_key,
                user_id=user.id,
                order_id=order.id,
                request_hash=request_hash,
            )
        )

    notifications.order_placed(db, order)
    db.commit()
    db.refresh(order)
    return order, True


def accept_order(db: Session, order: Order, actor: User, prep_minutes: int) -> Order:
    """Accept confirms the prep estimate: PLACED -> ACCEPTED -> PREPARING."""
    if order.status != STATUS_PLACED:
        raise bad_request(f"Only a placed order can be accepted (now {order.status})")
    order.prep_minutes = prep_minutes
    record_transition(db, order, STATUS_ACCEPTED, actor)
    from app.models.common import utcnow

    order.accepted_at = utcnow()
    record_transition(db, order, STATUS_PREPARING, actor)
    notifications.order_accepted(db, order)
    db.commit()
    db.refresh(order)
    return order


def reject_order(db: Session, order: Order, actor: User, reason: str) -> Order:
    if order.status != STATUS_PLACED:
        raise bad_request(f"Only a placed order can be rejected (now {order.status})")
    record_transition(db, order, STATUS_REJECTED, actor, reason=reason)
    db.commit()
    db.refresh(order)
    return order


def mark_ready(db: Session, order: Order, actor: User) -> Order:
    if order.status != STATUS_PREPARING:
        raise bad_request(f"Only a preparing order can be marked ready (now {order.status})")
    from app.models.common import utcnow

    record_transition(db, order, STATUS_READY, actor)
    order.ready_at = utcnow()
    db.commit()
    db.refresh(order)
    return order


def complete_pickup(db: Session, order: Order, actor: User) -> Order:
    if order.fulfillment_type != FULFILLMENT_PICKUP:
        raise bad_request("Only pickup orders can be completed by the restaurant")
    if order.status != STATUS_READY:
        raise bad_request(f"Only a ready order can be completed (now {order.status})")
    from app.models.common import utcnow

    record_transition(db, order, STATUS_COMPLETED, actor)
    order.completed_at = utcnow()
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, order: Order, actor: User | None, reason: str | None) -> Order:
    if order.status not in CANCELLABLE_STATUSES:
        raise bad_request(
            f"An order in {order.status} cannot be cancelled",
            code="invalid_transition",
        )
    from app.models.common import utcnow

    record_transition(db, order, STATUS_CANCELLED, actor, reason=reason)
    order.cancelled_at = utcnow()
    order.cancel_reason = reason
    notifications.order_cancelled(db, order)
    db.commit()
    db.refresh(order)
    return order


def issue_refund(
    db: Session, order: Order, actor: User, amount_cents: int | None, reason: str | None
):
    """Issue a refund with offsetting ledger entries. A full refund moves
    the order to REFUNDED."""
    from app.models.payments import Refund

    if order.status == STATUS_REFUNDED:
        raise conflict("This order has already been fully refunded")
    if order.status in (STATUS_CANCELLED, STATUS_REJECTED, STATUS_FAILED):
        raise bad_request(f"A {order.status} order cannot be refunded")
    amount = amount_cents if amount_cents is not None else order.total_cents
    if amount <= 0:
        raise bad_request("Refund amount must be greater than zero")
    if amount > order.total_cents:
        raise bad_request("Refund amount cannot exceed the order total")
    already_refunded = sum(r.amount_cents for r in order.refunds)
    if already_refunded + amount > order.total_cents:
        raise bad_request("Refund amount exceeds the remaining refundable total")

    refund = Refund(
        order_id=order.id,
        payment_id=order.payment_id,
        amount_cents=amount,
        reason=reason,
        issued_by=actor.id,
        status="issued",
    )
    db.add(refund)
    ledger_service.write_refund_entries(db, order, amount)
    if already_refunded + amount >= order.total_cents:
        record_transition(db, order, STATUS_REFUNDED, actor, reason=reason)
    db.commit()
    db.refresh(refund)
    return refund
