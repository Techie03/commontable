"""Dispatch router: serviceability, board, assign, override."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.errors import not_found
from app.db.session import get_db
from app.models.drivers import TASK_ACCEPTED, TASK_OFFERED, Driver
from app.models.identity import ROLE_ADMIN, ROLE_DISPATCHER, User
from app.models.orders import ACTIVE_STATUSES, STATUS_READY, Order
from app.schemas.orders import (
    AssignRequest,
    OverrideRequest,
    ServiceabilityOut,
    order_to_out,
    task_to_out,
)
from app.services import dispatch as dispatch_service
from app.services.orders import find_zone_for_postal_code
from app.services.websocket import manager

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@router.get("/serviceability", response_model=ServiceabilityOut)
def serviceability(
    postal_code: str | None = None,
    city: str | None = None,
    db: Session = Depends(get_db),
):
    """Public. Primary check is the zone postal-code list."""
    if not postal_code:
        return ServiceabilityOut(serviceable=False, fulfillment_options=[])
    zone = find_zone_for_postal_code(db, postal_code)
    if zone is None:
        return ServiceabilityOut(serviceable=False, fulfillment_options=[])
    return ServiceabilityOut(
        serviceable=True,
        zone_id=zone.id,
        zone_name=zone.name,
        fulfillment_options=["pickup", "standard"],
    )


@router.get("/board")
def board(
    user: User = Depends(require_roles(ROLE_DISPATCHER, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """Active orders, ready signals, and online drivers (with driver ids,
    which the dispatcher needs to call POST /dispatch/assign)."""
    active = (
        db.query(Order)
        .filter(Order.status.in_(ACTIVE_STATUSES))
        .order_by(Order.placed_at)
        .all()
    )
    ready = [o for o in active if o.status == STATUS_READY]
    online_drivers = (
        db.query(Driver).filter(Driver.online.is_(True)).all()
    )
    return {
        "active_orders": [order_to_out(o) for o in active],
        "ready_orders": [order_to_out(o) for o in ready],
        "online_drivers": [
            {
                "driver_id": d.id,
                "user_id": d.user_id,
                "name": d.user.full_name or d.user.email,
                "onboarding_status": d.onboarding_status,
                "online": d.online,
            }
            for d in online_drivers
        ],
    }


@router.post("/assign")
async def assign(
    body: AssignRequest,
    user: User = Depends(require_roles(ROLE_DISPATCHER, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == body.order_id).first()
    if order is None:
        raise not_found("Order not found")
    driver = db.query(Driver).filter(Driver.id == body.driver_id).first()
    if driver is None:
        raise not_found("Driver not found")
    task = dispatch_service.assign_driver(db, order, driver, user)
    task_out = task_to_out(task)
    await manager.broadcast(
        manager.driver_channel(driver.id),
        "offer.created",
        {
            "task_id": task.id,
            "order_id": order.id,
            "pay_cents": task.offered_pay_cents,
            "restaurant_name": task_out.restaurant_name,
            "pickup_address": task_out.pickup_address,
            "dropoff_address": task_out.dropoff_address,
            "distance_miles": None,
            "eta_minutes": None,
            "distance_estimate": "estimate unavailable",
        },
    )
    await manager.broadcast(
        manager.order_channel(order.id),
        "order.status_changed",
        {
            "order_id": order.id,
            "from_status": "READY",
            "to_status": "ASSIGNED",
        },
    )
    await manager.broadcast(
        manager.order_channel(order.id),
        "order.driver_assigned",
        {
            "order_id": order.id,
            "driver_name": driver.user.full_name or driver.user.email,
        },
    )
    return task_to_out(task)


@router.post("/override")
async def override(
    body: OverrideRequest,
    user: User = Depends(require_roles(ROLE_DISPATCHER, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == body.order_id).first()
    if order is None:
        raise not_found("Order not found")
    new_driver = db.query(Driver).filter(Driver.id == body.driver_id).first()
    if new_driver is None:
        raise not_found("Driver not found")
    # Find the currently offered/accepted task to withdraw its offer event.
    from app.models.drivers import DeliveryTask

    current_task = (
        db.query(DeliveryTask)
        .filter(
            DeliveryTask.order_id == order.id,
            DeliveryTask.status.in_([TASK_OFFERED, TASK_ACCEPTED]),
        )
        .order_by(DeliveryTask.id.desc())
        .first()
    )
    old_driver_id = current_task.driver_id if current_task else None
    old_task_id = current_task.id if current_task else None
    task = dispatch_service.override_assignment(db, order, new_driver, user, body.reason)
    if old_driver_id is not None:
        await manager.broadcast(
            manager.driver_channel(old_driver_id),
            "offer.withdrawn",
            {"task_id": old_task_id},
        )
    task_out = task_to_out(task)
    await manager.broadcast(
        manager.driver_channel(new_driver.id),
        "offer.created",
        {
            "task_id": task.id,
            "order_id": order.id,
            "pay_cents": task.offered_pay_cents,
            "restaurant_name": task_out.restaurant_name,
            "pickup_address": task_out.pickup_address,
            "dropoff_address": task_out.dropoff_address,
            "distance_miles": None,
            "eta_minutes": None,
            "distance_estimate": "estimate unavailable",
        },
    )
    await manager.broadcast(
        manager.order_channel(order.id),
        "order.driver_assigned",
        {
            "order_id": order.id,
            "driver_name": new_driver.user.full_name or new_driver.user.email,
        },
    )
    return task_to_out(task)
