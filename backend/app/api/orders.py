"""Orders router: placement, lifecycle actions, events, ratings."""

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_user,
    is_admin,
    is_dispatcher_or_admin,
    require_order_access,
    require_restaurant_access,
)
from app.core.errors import bad_request, forbidden, not_found
from app.db.session import get_db
from app.models.identity import (
    RESTAURANT_ROLES,
    ROLE_CUSTOMER,
    User,
)
from app.models.orders import (
    CHANNEL_DIRECT2DOOR,
    STATUS_COMPLETED,
    STATUS_DELIVERED,
    Order,
    Rating,
    StatusEvent,
)
from app.models.restaurants import Restaurant
from app.schemas.orders import (
    AcceptOrderRequest,
    CancelOrderRequest,
    OrderCreate,
    OrderOut,
    RatingRequest,
    RejectOrderRequest,
    StatusEventOut,
    order_to_out,
)
from app.services import orders as order_service
from app.services.websocket import manager

router = APIRouter(prefix="/orders", tags=["orders"])


async def _broadcast_status(order: Order, from_status: str | None, to_status: str):
    await manager.broadcast(
        manager.order_channel(order.id),
        "order.status_changed",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "from_status": from_status,
            "to_status": to_status,
        },
    )


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(
    body: OrderCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place an order. Customers place app orders; restaurant staff place
    Direct2Door orders (channel direct2door) with a customer name + phone.
    Returns 201. A retried request with the same Idempotency-Key returns the
    original order."""
    restaurant = (
        db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    )
    if restaurant is None:
        raise not_found("Restaurant not found")
    if body.channel == CHANNEL_DIRECT2DOOR:
        require_restaurant_access(body.restaurant_id, user, RESTAURANT_ROLES)
        if not body.customer_name or not body.customer_phone:
            raise bad_request(
                "Direct2Door orders need a customer name and phone number"
            )
    else:
        if not user.has_role(ROLE_CUSTOMER) and not is_admin(user):
            raise forbidden("Only customers can place app orders")
        if body.channel != "app":
            raise bad_request("Channel must be 'app' or 'direct2door'")

    order, created = order_service.place_order(
        db,
        user=user,
        restaurant_id=body.restaurant_id,
        items=[it.model_dump() for it in body.items],
        fulfillment_type=body.fulfillment_type,
        delivery_address=(
            body.delivery_address.model_dump() if body.delivery_address else None
        ),
        tip_cents=body.tip_cents,
        channel=body.channel,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        idempotency_key=idempotency_key,
    )
    if created:
        await manager.broadcast(
            manager.DISPATCH_CHANNEL,
            "order.placed",
            {"order_id": order.id, "order_number": order.order_number},
        )
        await manager.broadcast(
            manager.restaurant_channel(order.restaurant_id),
            "order.placed",
            {"order_id": order.id, "order_number": order.order_number},
        )
    return order_to_out(order)


@router.get("", response_model=dict)
def list_orders(
    status: str | None = None,
    restaurant_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Scoped by role: customers see only their own orders; restaurant staff
    only theirs; dispatcher/admin see all."""
    query = db.query(Order).order_by(Order.placed_at.desc(), Order.id.desc())
    if status:
        query = query.filter(Order.status == status)
    if restaurant_id is not None:
        query = query.filter(Order.restaurant_id == restaurant_id)
    if is_dispatcher_or_admin(user):
        pass
    elif user.has_role(*RESTAURANT_ROLES):
        ids = user.restaurant_ids(*RESTAURANT_ROLES)
        query = query.filter(Order.restaurant_id.in_(ids))
    else:
        customer = user.customer_profile
        query = query.filter(
            Order.customer_id == (customer.id if customer else -1)
        )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [order_to_out(o) for o in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise not_found("Order not found")
    require_order_access(order, user)
    return order_to_out(order)


@router.get("/{order_id}/events")
def get_order_events(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise not_found("Order not found")
    require_order_access(order, user)
    events = (
        db.query(StatusEvent)
        .filter(StatusEvent.order_id == order.id)
        .order_by(StatusEvent.created_at, StatusEvent.id)
        .all()
    )
    return {
        "items": [
            StatusEventOut(
                id=e.id,
                from_status=e.from_status,
                to_status=e.to_status,
                actor_user_id=e.actor_user_id,
                reason=e.reason,
                created_at=e.created_at,
            )
            for e in events
        ],
        "page": 1,
        "page_size": len(events),
        "total": len(events),
    }


def _load_order_for_restaurant(
    order_id: int, user: User, db: Session
) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise not_found("Order not found")
    require_restaurant_access(order.restaurant_id, user, RESTAURANT_ROLES)
    return order


@router.post("/{order_id}/accept", response_model=OrderOut)
async def accept_order(
    order_id: int,
    body: AcceptOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _load_order_for_restaurant(order_id, user, db)
    order = order_service.accept_order(db, order, user, body.prep_minutes)
    # Two transitions, two events (coordination note 1).
    await _broadcast_status(order, "PLACED", "ACCEPTED")
    await _broadcast_status(order, "ACCEPTED", "PREPARING")
    return order_to_out(order)


@router.post("/{order_id}/reject", response_model=OrderOut)
async def reject_order(
    order_id: int,
    body: RejectOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _load_order_for_restaurant(order_id, user, db)
    from_status = order.status
    order = order_service.reject_order(db, order, user, body.reason)
    await _broadcast_status(order, from_status, order.status)
    return order_to_out(order)


@router.post("/{order_id}/ready", response_model=OrderOut)
async def ready_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _load_order_for_restaurant(order_id, user, db)
    from_status = order.status
    order = order_service.mark_ready(db, order, user)
    await _broadcast_status(order, from_status, order.status)
    await manager.broadcast(
        manager.DISPATCH_CHANNEL,
        "order.ready",
        {"order_id": order.id, "order_number": order.order_number},
    )
    return order_to_out(order)


@router.post("/{order_id}/complete", response_model=OrderOut)
async def complete_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _load_order_for_restaurant(order_id, user, db)
    from_status = order.status
    order = order_service.complete_pickup(db, order, user)
    await _broadcast_status(order, from_status, order.status)
    return order_to_out(order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    body: CancelOrderRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise not_found("Order not found")
    # Customer owner, restaurant staff of it, or admin may cancel.
    is_owner = order.customer is not None and order.customer.user_id == user.id
    is_staff = user.has_role(*RESTAURANT_ROLES, scope_id=order.restaurant_id)
    if not (is_owner or is_staff or is_admin(user)):
        raise forbidden("You cannot cancel this order")
    from_status = order.status
    order = order_service.cancel_order(
        db, order, user, body.reason if body else None
    )
    await _broadcast_status(order, from_status, order.status)
    await manager.broadcast(
        manager.restaurant_channel(order.restaurant_id),
        "order.cancelled",
        {"order_id": order.id, "order_number": order.order_number},
    )
    return order_to_out(order)


@router.post("/{order_id}/ratings", status_code=201)
def rate_order(
    order_id: int,
    body: RatingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise not_found("Order not found")
    if order.customer is None or order.customer.user_id != user.id:
        raise forbidden("Only the customer who placed this order can rate it")
    if order.status not in (STATUS_DELIVERED, STATUS_COMPLETED):
        raise bad_request("An order can only be rated after delivery")
    existing = db.query(Rating).filter(Rating.order_id == order.id).first()
    if existing is not None:
        raise bad_request("This order already has a rating")
    driver_id = None
    delivered_task = next(
        (t for t in order.delivery_tasks if t.status == "delivered"), None
    )
    if delivered_task is not None:
        driver_id = delivered_task.driver_id
    rating = Rating(
        order_id=order.id,
        customer_id=order.customer_id,
        driver_id=driver_id,
        restaurant_id=order.restaurant_id,
        score=body.score,
        comment=body.comment,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return {
        "id": rating.id,
        "order_id": rating.order_id,
        "score": rating.score,
        "comment": rating.comment,
    }
