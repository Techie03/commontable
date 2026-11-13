"""Order, dispatch, driver, payment, ledger, admin, notification schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.restaurants import AddressIn, AddressOut, address_to_out


class OrderItemModifierIn(BaseModel):
    modifier_id: int


class OrderItemIn(BaseModel):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1)
    modifiers: list[OrderItemModifierIn] = []


class OrderCreate(BaseModel):
    restaurant_id: int
    items: list[OrderItemIn] = Field(min_length=1)
    fulfillment_type: str = "standard"
    delivery_address: AddressIn | None = None
    tip_cents: int = Field(default=0, ge=0)
    channel: str = "app"
    customer_name: str | None = None
    customer_phone: str | None = None


class OrderItemOut(BaseModel):
    id: int
    menu_item_id: int
    name_snapshot: str
    price_snapshot_cents: int
    quantity: int
    modifiers_snapshot: list[dict] = []
    line_total_cents: int


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    restaurant_id: int
    restaurant_name: str | None = None
    channel: str
    fulfillment_type: str
    status: str
    delivery_address: AddressOut | None = None
    subtotal_cents: int
    delivery_fee_cents: int
    tax_cents: int
    tip_cents: int
    total_cents: int
    currency: str
    checkout_snapshot: dict
    prep_minutes: int | None = None
    items: list[OrderItemOut] = []
    placed_at: datetime | None = None
    accepted_at: datetime | None = None
    ready_at: datetime | None = None
    delivered_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None


class StatusEventOut(BaseModel):
    id: int
    from_status: str | None = None
    to_status: str
    actor_user_id: int | None = None
    reason: str | None = None
    created_at: datetime | None = None


class AcceptOrderRequest(BaseModel):
    prep_minutes: int = Field(ge=1, le=240)


class RejectOrderRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class CancelOrderRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class RatingRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


def order_to_out(order) -> OrderOut:
    return OrderOut(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        restaurant_id=order.restaurant_id,
        restaurant_name=order.restaurant.name if order.restaurant else None,
        channel=order.channel,
        fulfillment_type=order.fulfillment_type,
        status=order.status,
        delivery_address=address_to_out(order.delivery_address),
        subtotal_cents=order.subtotal_cents,
        delivery_fee_cents=order.delivery_fee_cents,
        tax_cents=order.tax_cents,
        tip_cents=order.tip_cents,
        total_cents=order.total_cents,
        currency=order.currency,
        checkout_snapshot=order.checkout_snapshot,
        prep_minutes=order.prep_minutes,
        items=[
            OrderItemOut(
                id=i.id,
                menu_item_id=i.menu_item_id,
                name_snapshot=i.name_snapshot,
                price_snapshot_cents=i.price_snapshot_cents,
                quantity=i.quantity,
                modifiers_snapshot=i.modifiers_snapshot or [],
                line_total_cents=i.line_total_cents,
            )
            for i in order.items
        ],
        placed_at=order.placed_at,
        accepted_at=order.accepted_at,
        ready_at=order.ready_at,
        delivered_at=order.delivered_at,
        completed_at=order.completed_at,
        cancelled_at=order.cancelled_at,
        cancel_reason=order.cancel_reason,
    )


# -- Dispatch / drivers -------------------------------------------------

class ServiceabilityOut(BaseModel):
    serviceable: bool
    zone_id: int | None = None
    zone_name: str | None = None
    fulfillment_options: list[str] = []


class AssignRequest(BaseModel):
    order_id: int
    driver_id: int


class OverrideRequest(BaseModel):
    order_id: int
    driver_id: int
    reason: str = Field(min_length=1, max_length=500)


class DeliveryTaskOut(BaseModel):
    id: int
    order_id: int
    order_number: str | None = None
    driver_id: int
    status: str
    # Canonical offer pay field (matches the WS offer.created event).
    pay_cents: int
    offered_pay_cents: int
    restaurant_name: str | None = None
    pickup_address: str | None = None
    dropoff_address: str | None = None
    distance_miles: float | None = None
    eta_minutes: int | None = None
    distance_estimate: str = "estimate unavailable"
    accepted_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None
    proof_note: str | None = None
    created_at: datetime | None = None


def task_to_out(task) -> DeliveryTaskOut:
    order = task.order
    pickup = None
    if order and order.restaurant_location and order.restaurant_location.address:
        pickup = order.restaurant_location.address.formatted()
    dropoff = None
    if order and order.delivery_address:
        dropoff = order.delivery_address.formatted()
    return DeliveryTaskOut(
        id=task.id,
        order_id=task.order_id,
        order_number=order.order_number if order else None,
        driver_id=task.driver_id,
        status=task.status,
        pay_cents=task.offered_pay_cents,
        offered_pay_cents=task.offered_pay_cents,
        restaurant_name=order.restaurant.name if order and order.restaurant else None,
        pickup_address=pickup,
        dropoff_address=dropoff,
        distance_miles=None,
        eta_minutes=None,
        distance_estimate="estimate unavailable",
        accepted_at=task.accepted_at,
        picked_up_at=task.picked_up_at,
        delivered_at=task.delivered_at,
        proof_note=task.proof_note,
        created_at=task.created_at,
    )


class AvailabilityRequest(BaseModel):
    online: bool


class DriverOut(BaseModel):
    id: int
    user_id: int
    full_name: str | None = None
    email: str | None = None
    onboarding_status: str
    license_verified: bool
    online: bool


class DeliverRequest(BaseModel):
    proof_note: str | None = Field(default=None, max_length=500)


class IssueRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)


# -- Payments / ledger / refunds -----------------------------------------

class PaymentIntentRequest(BaseModel):
    order_id: int


class PaymentIntentOut(BaseModel):
    provider: str
    status: str
    payment_id: int | None = None
    order_id: int
    amount_cents: int
    currency: str
    message: str


class LedgerEntryOut(BaseModel):
    id: int
    order_id: int | None = None
    entry_type: str
    direction: str
    amount_cents: int
    currency: str
    description: str | None = None
    created_at: datetime | None = None


class RefundRequest(BaseModel):
    amount_cents: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=500)


class RefundOut(BaseModel):
    id: int
    order_id: int
    amount_cents: int
    reason: str | None = None
    status: str
    created_at: datetime | None = None


# -- Admin ----------------------------------------------------------------

class ZoneCreate(BaseModel):
    name: str
    boundary_geojson: dict | None = None
    postal_codes: list[str] = []
    tax_rate_bps: int = Field(default=825, ge=0)
    hours_json: dict | None = None
    active: bool = True


class ZoneUpdate(BaseModel):
    name: str | None = None
    boundary_geojson: dict | None = None
    postal_codes: list[str] | None = None
    tax_rate_bps: int | None = None
    hours_json: dict | None = None
    active: bool | None = None


class ZoneOut(BaseModel):
    id: int
    name: str
    boundary_geojson: dict | None = None
    postal_codes: list[str] = []
    tax_rate_bps: int
    hours_json: dict | None = None
    active: bool


class PricingRuleCreate(BaseModel):
    service_zone_id: int | None = None
    rule_key: str
    value_cents: int = Field(ge=0)
    fulfillment_type: str | None = None
    active: bool = True


class PricingRuleUpdate(BaseModel):
    value_cents: int | None = Field(default=None, ge=0)
    active: bool | None = None


class PricingRuleOut(BaseModel):
    id: int
    service_zone_id: int | None = None
    rule_key: str
    value_cents: int
    fulfillment_type: str | None = None
    active: bool


class RoleChangeRequest(BaseModel):
    add: list[str] = []
    remove: list[str] = []
    scope_restaurant_id: int | None = None


class SupportTicketOut(BaseModel):
    id: int
    order_id: int | None = None
    reporter_user_id: int
    type: str
    status: str
    description: str
    resolution: str | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None


class SupportTicketUpdate(BaseModel):
    status: str | None = None
    resolution: str | None = None


# -- Notifications ---------------------------------------------------------

class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str | None = None
    order_id: int | None = None
    read: bool
    created_at: datetime | None = None
