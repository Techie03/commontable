"""Admin router: users, restaurants, drivers, zones, pricing, metrics,
support, settlements, and the platform ledger."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from shapely.geometry import shape as geojson_shape
from shapely import wkt as shapely_wkt
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.errors import bad_request, not_found
from app.db.session import get_db
from app.models.drivers import ONBOARDING_APPROVED, Driver
from app.models.geo import ServiceZone
from app.models.identity import ALL_ROLES, RESTAURANT_ROLES, ROLE_ADMIN, Role, User, UserRole
from app.models.misc import SupportTicket
from app.models.orders import Order
from app.models.payments import (
    DIRECTION_CREDIT,
    DIRECTION_DEBIT,
    ENTRY_DELIVERY_FEE_REVENUE,
    ENTRY_PLATFORM_FEE_REVENUE,
    ENTRY_RESTAURANT_PAYABLE,
    LedgerEntry,
    PricingRule,
)
from app.models.restaurants import RESTAURANT_STATUSES, STATUS_ACTIVE, Restaurant
from app.schemas.auth import UserOut, user_to_out
from app.schemas.orders import (
    LedgerEntryOut,
    PricingRuleCreate,
    PricingRuleOut,
    PricingRuleUpdate,
    RoleChangeRequest,
    SupportTicketOut,
    SupportTicketUpdate,
    ZoneCreate,
    ZoneOut,
    ZoneUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = require_roles(ROLE_ADMIN)


def _paginate(query, page: int, page_size: int, to_out):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [to_out(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


# -- Users ---------------------------------------------------------------

@router.get("/users")
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    query = db.query(User).order_by(User.created_at.desc())
    return _paginate(query, page, page_size, user_to_out)


@router.patch("/users/{user_id}/roles", response_model=UserOut)
def change_user_roles(
    user_id: int,
    body: RoleChangeRequest,
    admin: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise not_found("User not found")
    for name in body.add + body.remove:
        if name not in ALL_ROLES:
            raise bad_request(f"Unknown role: {name}")
    roles = {r.name: r for r in db.query(Role).all()}
    for name in body.add:
        role = roles.get(name)
        if role is None:
            role = Role(name=name)
            db.add(role)
            db.flush()
            roles[name] = role
        scope_id = body.scope_restaurant_id if name in RESTAURANT_ROLES else None
        existing = (
            db.query(UserRole)
            .filter(
                UserRole.user_id == target.id,
                UserRole.role_id == role.id,
                UserRole.scope_id == scope_id,
            )
            .first()
        )
        if existing is None:
            db.add(
                UserRole(
                    user_id=target.id,
                    role_id=role.id,
                    scope_type="restaurant" if scope_id is not None else None,
                    scope_id=scope_id,
                    granted_by=admin.id,
                )
            )
        if name == "driver" and target.driver_profile is None:
            db.add(Driver(user_id=target.id))
    for name in body.remove:
        role = roles.get(name)
        if role is None:
            continue
        grants = (
            db.query(UserRole)
            .filter(UserRole.user_id == target.id, UserRole.role_id == role.id)
            .all()
        )
        for grant in grants:
            db.delete(grant)
    db.commit()
    db.refresh(target)
    return user_to_out(target)


# -- Restaurants ----------------------------------------------------------

@router.get("/restaurants")
def list_all_restaurants(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    """All restaurants including prospects (admin only). Prospects are
    unclaimed census data, not partners."""
    from app.schemas.restaurants import restaurant_to_out

    query = db.query(Restaurant).order_by(Restaurant.name)
    if status:
        if status not in RESTAURANT_STATUSES:
            raise bad_request(f"Unknown restaurant status: {status}")
        query = query.filter(Restaurant.status == status)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [restaurant_to_out(r) for r in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "note": (
            "Prospect restaurants are unclaimed census listings, not partners. "
            "They never appear in customer ordering."
        ),
    }


@router.post("/restaurants/{restaurant_id}/approve")
def approve_restaurant(
    restaurant_id: int,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    from app.models.common import utcnow
    from app.schemas.restaurants import restaurant_to_out

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    restaurant.status = STATUS_ACTIVE
    restaurant.onboarding_approved_at = utcnow()
    db.commit()
    db.refresh(restaurant)
    return restaurant_to_out(restaurant)


@router.get("/drivers")
def list_drivers(
    onboarding_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    """List driver profiles (admin). Returns driver-profile ids, which is
    what the approve endpoint takes."""
    query = db.query(Driver)
    if onboarding_status:
        query = query.filter(Driver.onboarding_status == onboarding_status)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "driver_id": d.id,
                "user_id": d.user_id,
                "onboarding_status": d.onboarding_status,
                "license_verified": d.license_verified,
                "online": d.online,
                "created_at": d.created_at,
            }
            for d in items
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/drivers/{driver_id}/approve")
def approve_driver(
    driver_id: int,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    # The path id is normally the driver-profile id. Fall back to a user id
    # lookup so callers holding only the user id (e.g. the admin console's
    # users-derived driver list) can still approve.
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if driver is None:
        driver = db.query(Driver).filter(Driver.user_id == driver_id).first()
    if driver is None:
        raise not_found("Driver not found")
    driver.onboarding_status = ONBOARDING_APPROVED
    db.commit()
    db.refresh(driver)
    return {
        "driver_id": driver.id,
        "user_id": driver.user_id,
        "onboarding_status": driver.onboarding_status,
    }


# -- Zones ----------------------------------------------------------------

def _geojson_to_wkt(geojson: dict | None) -> str | None:
    if geojson is None:
        return None
    try:
        return geojson_shape(geojson).wkt
    except Exception as exc:
        raise bad_request(f"Invalid boundary GeoJSON: {exc}")


def _wkt_to_geojson(wkt: str | None) -> dict | None:
    if wkt is None:
        return None
    try:
        geom = shapely_wkt.loads(wkt)
        from shapely.geometry import mapping

        return mapping(geom)
    except Exception:
        return None


def _zone_to_out(zone: ServiceZone) -> ZoneOut:
    return ZoneOut(
        id=zone.id,
        name=zone.name,
        boundary_geojson=_wkt_to_geojson(zone.boundary),
        postal_codes=zone.postal_codes or [],
        tax_rate_bps=zone.tax_rate_bps,
        hours_json=zone.hours_json,
        active=zone.active,
    )


@router.get("/zones")
def list_zones(user: User = Depends(AdminUser), db: Session = Depends(get_db)):
    zones = db.query(ServiceZone).order_by(ServiceZone.name).all()
    return {
        "items": [_zone_to_out(z) for z in zones],
        "page": 1,
        "page_size": len(zones),
        "total": len(zones),
    }


@router.post("/zones", response_model=ZoneOut, status_code=201)
def create_zone(
    body: ZoneCreate,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    zone = ServiceZone(
        name=body.name,
        boundary=_geojson_to_wkt(body.boundary_geojson),
        postal_codes=body.postal_codes,
        tax_rate_bps=body.tax_rate_bps,
        hours_json=body.hours_json,
        active=body.active,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return _zone_to_out(zone)


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
def update_zone(
    zone_id: int,
    body: ZoneUpdate,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    zone = db.query(ServiceZone).filter(ServiceZone.id == zone_id).first()
    if zone is None:
        raise not_found("Zone not found")
    data = body.model_dump(exclude_unset=True)
    if "boundary_geojson" in data:
        zone.boundary = _geojson_to_wkt(data.pop("boundary_geojson"))
    for field, value in data.items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return _zone_to_out(zone)


# -- Pricing ---------------------------------------------------------------

@router.get("/pricing")
def list_pricing(
    zone_id: int | None = None,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    query = db.query(PricingRule).order_by(PricingRule.rule_key)
    if zone_id is not None:
        query = query.filter(PricingRule.service_zone_id == zone_id)
    rules = query.all()
    return {
        "items": [
            PricingRuleOut(
                id=r.id,
                service_zone_id=r.service_zone_id,
                rule_key=r.rule_key,
                value_cents=r.value_cents,
                fulfillment_type=r.fulfillment_type,
                active=r.active,
            )
            for r in rules
        ],
        "page": 1,
        "page_size": len(rules),
        "total": len(rules),
    }


@router.post("/pricing", response_model=PricingRuleOut, status_code=201)
def create_pricing_rule(
    body: PricingRuleCreate,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    rule = PricingRule(
        service_zone_id=body.service_zone_id,
        rule_key=body.rule_key,
        value_cents=body.value_cents,
        fulfillment_type=body.fulfillment_type,
        active=body.active,
        created_by=user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return PricingRuleOut(
        id=rule.id,
        service_zone_id=rule.service_zone_id,
        rule_key=rule.rule_key,
        value_cents=rule.value_cents,
        fulfillment_type=rule.fulfillment_type,
        active=rule.active,
    )


@router.patch("/pricing/{rule_id}", response_model=PricingRuleOut)
def update_pricing_rule(
    rule_id: int,
    body: PricingRuleUpdate,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    rule = db.query(PricingRule).filter(PricingRule.id == rule_id).first()
    if rule is None:
        raise not_found("Pricing rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return PricingRuleOut(
        id=rule.id,
        service_zone_id=rule.service_zone_id,
        rule_key=rule.rule_key,
        value_cents=rule.value_cents,
        fulfillment_type=rule.fulfillment_type,
        active=rule.active,
    )


# -- Metrics, support, settlements, ledger --------------------------------

@router.get("/metrics")
def metrics(user: User = Depends(AdminUser), db: Session = Depends(get_db)):
    """Basic metrics, all derived from real rows. Nothing invented."""
    orders = db.query(Order).all()
    by_status: dict[str, int] = {}
    for order in orders:
        by_status[order.status] = by_status.get(order.status, 0) + 1
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    orders_today = [o for o in orders if o.placed_at and o.placed_at >= today_start]
    fee_entries = (
        db.query(LedgerEntry)
        .filter(
            LedgerEntry.entry_type.in_(
                [ENTRY_DELIVERY_FEE_REVENUE, ENTRY_PLATFORM_FEE_REVENUE]
            ),
            LedgerEntry.direction == DIRECTION_CREDIT,
            LedgerEntry.created_at >= today_start,
        )
        .all()
    )
    fees_today_cents = sum(e.amount_cents for e in fee_entries)
    prep_durations = [
        (o.ready_at - o.accepted_at).total_seconds() / 60
        for o in orders
        if o.accepted_at and o.ready_at
    ]
    avg_prep_minutes = (
        round(sum(prep_durations) / len(prep_durations), 1) if prep_durations else None
    )
    delivery_durations = [
        (o.delivered_at - o.placed_at).total_seconds() / 60
        for o in orders
        if o.placed_at and o.delivered_at
    ]
    avg_delivery_minutes = (
        round(sum(delivery_durations) / len(delivery_durations), 1)
        if delivery_durations
        else None
    )
    return {
        "orders_by_status": by_status,
        "orders_today": len(orders_today),
        "total_orders": len(orders),
        "revenue_fees_today_cents": fees_today_cents,
        "avg_prep_minutes": avg_prep_minutes,
        "avg_delivery_minutes": avg_delivery_minutes,
        "on_time_proxy": {
            "avg_delivery_minutes": avg_delivery_minutes,
            "note": (
                "No promised delivery window exists in the slice, so on-time "
                "rate is not computed. Average placed to delivered time is "
                "shown instead."
            ),
        },
    }


@router.get("/support")
def list_support(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    query = db.query(SupportTicket).order_by(SupportTicket.created_at.desc())
    if status:
        query = query.filter(SupportTicket.status == status)
    return _paginate(
        query,
        page,
        page_size,
        lambda t: SupportTicketOut(
            id=t.id,
            order_id=t.order_id,
            reporter_user_id=t.reporter_user_id,
            type=t.type,
            status=t.status,
            description=t.description,
            resolution=t.resolution,
            created_at=t.created_at,
            resolved_at=t.resolved_at,
        ),
    )


@router.patch("/support/{ticket_id}", response_model=SupportTicketOut)
def update_support(
    ticket_id: int,
    body: SupportTicketUpdate,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if ticket is None:
        raise not_found("Support ticket not found")
    if body.status is not None:
        ticket.status = body.status
        if body.status in ("resolved", "closed"):
            from app.models.common import utcnow

            ticket.resolved_at = utcnow()
    if body.resolution is not None:
        ticket.resolution = body.resolution
    db.commit()
    db.refresh(ticket)
    return SupportTicketOut(
        id=ticket.id,
        order_id=ticket.order_id,
        reporter_user_id=ticket.reporter_user_id,
        type=ticket.type,
        status=ticket.status,
        description=ticket.description,
        resolution=ticket.resolution,
        created_at=ticket.created_at,
        resolved_at=ticket.resolved_at,
    )


@router.get("/settlements")
def settlements(
    restaurant_id: int | None = None,
    period: str | None = None,
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    """Settlement summaries computed from the ledger. No money movement.
    period is YYYY-MM; omitted means all time."""
    query = (
        db.query(LedgerEntry)
        .join(Order, LedgerEntry.order_id == Order.id)
        .filter(LedgerEntry.entry_type == ENTRY_RESTAURANT_PAYABLE)
    )
    if restaurant_id is not None:
        query = query.filter(Order.restaurant_id == restaurant_id)
    entries = query.all()
    if period:
        try:
            year, month = (int(part) for part in period.split("-", 1))
        except ValueError:
            raise bad_request("period must look like YYYY-MM")
        entries = [
            e
            for e in entries
            if e.created_at and e.created_at.year == year and e.created_at.month == month
        ]
    by_restaurant: dict[int, int] = {}
    for entry in entries:
        delta = entry.amount_cents if entry.direction == DIRECTION_CREDIT else -entry.amount_cents
        by_restaurant[entry.order.restaurant_id] = (
            by_restaurant.get(entry.order.restaurant_id, 0) + delta
        )
    return {
        "period": period or "all",
        "settlements": [
            {
                "restaurant_id": rid,
                "restaurant_payable_cents": cents,
            }
            for rid, cents in sorted(by_restaurant.items())
        ],
        "note": "Computed from the ledger. No money has moved.",
    }


@router.get("/ledger")
def admin_ledger(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(AdminUser),
    db: Session = Depends(get_db),
):
    """Platform ledger view, paginated."""
    query = db.query(LedgerEntry).order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
    return _paginate(
        query,
        page,
        page_size,
        lambda e: LedgerEntryOut(
            id=e.id,
            order_id=e.order_id,
            entry_type=e.entry_type,
            direction=e.direction,
            amount_cents=e.amount_cents,
            currency=e.currency,
            description=e.description,
            created_at=e.created_at,
        ),
    )
