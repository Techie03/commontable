"""Notification service: rows created on the contract section 3 events.

Customer rows on: accepted, preparing, driver assigned, picked up, delivered.
Restaurant staff rows on: order placed, order cancelled.
"""

from sqlalchemy.orm import Session

from app.models.identity import RESTAURANT_ROLES, Role, UserRole
from app.models.misc import (
    NOTIF_DRIVER_ASSIGNED,
    NOTIF_ORDER_ACCEPTED,
    NOTIF_ORDER_CANCELLED,
    NOTIF_ORDER_DELIVERED,
    NOTIF_ORDER_PICKED_UP,
    NOTIF_ORDER_PLACED,
    NOTIF_ORDER_PREPARING,
    Notification,
)
from app.models.orders import Order


def _create(
    db: Session,
    user_id: int,
    notif_type: str,
    title: str,
    body: str | None,
    order_id: int | None,
) -> Notification:
    notif = Notification(
        user_id=user_id, type=notif_type, title=title, body=body, order_id=order_id
    )
    db.add(notif)
    return notif


def _restaurant_staff_user_ids(db: Session, restaurant_id: int) -> list[int]:
    role_ids = {
        r.id for r in db.query(Role).filter(Role.name.in_(RESTAURANT_ROLES)).all()
    }
    rows = (
        db.query(UserRole.user_id)
        .filter(
            UserRole.scope_id == restaurant_id,
            UserRole.role_id.in_(role_ids),
        )
        .distinct()
        .all()
    )
    return [user_id for (user_id,) in rows]


def notify_customer(
    db: Session, order: Order, notif_type: str, title: str, body: str | None = None
) -> Notification | None:
    """Notify the order's customer (skipped for Direct2Door orders with no
    CommonTable account)."""
    if order.customer is None:
        return None
    return _create(db, order.customer.user_id, notif_type, title, body, order.id)


def notify_restaurant(
    db: Session, order: Order, notif_type: str, title: str, body: str | None = None
) -> list[Notification]:
    notifs = []
    for user_id in _restaurant_staff_user_ids(db, order.restaurant_id):
        notifs.append(_create(db, user_id, notif_type, title, body, order.id))
    return notifs


def order_placed(db: Session, order: Order) -> None:
    notify_restaurant(
        db,
        order,
        NOTIF_ORDER_PLACED,
        f"New order {order.order_number}",
        "A new order arrived and is waiting for a decision.",
    )


def order_accepted(db: Session, order: Order) -> None:
    notify_customer(
        db, order, NOTIF_ORDER_ACCEPTED,
        f"Order {order.order_number} accepted",
        f"{order.restaurant.name} accepted your order.",
    )
    notify_customer(
        db, order, NOTIF_ORDER_PREPARING,
        f"Order {order.order_number} is being prepared",
        "The kitchen started preparing your order.",
    )


def driver_assigned(db: Session, order: Order, driver_name: str) -> None:
    notify_customer(
        db, order, NOTIF_DRIVER_ASSIGNED,
        f"Driver assigned to order {order.order_number}",
        f"{driver_name} will deliver your order.",
    )


def order_picked_up(db: Session, order: Order) -> None:
    notify_customer(
        db, order, NOTIF_ORDER_PICKED_UP,
        f"Order {order.order_number} picked up",
        "Your order is on its way.",
    )


def order_delivered(db: Session, order: Order) -> None:
    notify_customer(
        db, order, NOTIF_ORDER_DELIVERED,
        f"Order {order.order_number} delivered",
        "Your order was delivered. Enjoy your meal.",
    )


def order_cancelled(db: Session, order: Order) -> None:
    notify_restaurant(
        db, order, NOTIF_ORDER_CANCELLED,
        f"Order {order.order_number} cancelled",
        "This order was cancelled.",
    )
