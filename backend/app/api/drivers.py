"""Driver router: profile, offers, availability, earnings."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_driver_profile, require_roles
from app.core.errors import not_found
from app.db.session import get_db
from app.models.common import utcnow
from app.models.drivers import (
    TASK_ACCEPTED,
    TASK_DELIVERED,
    TASK_OFFERED,
    TASK_PICKED_UP,
    DeliveryTask,
    DriverShift,
)
from app.models.identity import ROLE_DRIVER, User
from app.schemas.orders import (
    AvailabilityRequest,
    DriverOut,
    task_to_out,
)
from app.services import dispatch as dispatch_service
from app.services.websocket import manager

router = APIRouter(prefix="/drivers/me", tags=["drivers"])


@router.get("", response_model=DriverOut)
def get_me(
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    driver = get_driver_profile(user, db)
    return DriverOut(
        id=driver.id,
        user_id=driver.user_id,
        full_name=user.full_name,
        email=user.email,
        onboarding_status=driver.onboarding_status,
        license_verified=driver.license_verified,
        online=driver.online,
    )


@router.get("/offers")
def my_offers(
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    """Pending offered tasks with full route + pay shown up front."""
    driver = get_driver_profile(user, db)
    tasks = (
        db.query(DeliveryTask)
        .filter(
            DeliveryTask.driver_id == driver.id,
            DeliveryTask.status == TASK_OFFERED,
        )
        .order_by(DeliveryTask.created_at)
        .all()
    )
    return {
        "items": [task_to_out(t) for t in tasks],
        "page": 1,
        "page_size": len(tasks),
        "total": len(tasks),
    }


@router.get("/tasks")
def my_tasks(
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    """The driver's active tasks (accepted or picked up). The driver page
    uses this to restore the active delivery after a refresh or on a
    different device, instead of relying on browser storage alone."""
    driver = get_driver_profile(user, db)
    tasks = (
        db.query(DeliveryTask)
        .filter(
            DeliveryTask.driver_id == driver.id,
            DeliveryTask.status.in_([TASK_ACCEPTED, TASK_PICKED_UP]),
        )
        .order_by(DeliveryTask.created_at)
        .all()
    )
    return {
        "items": [task_to_out(t) for t in tasks],
        "page": 1,
        "page_size": len(tasks),
        "total": len(tasks),
    }


@router.post("/offers/{task_id}/accept")
async def accept_offer(
    task_id: int,
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    driver = get_driver_profile(user, db)
    task = (
        db.query(DeliveryTask)
        .filter(DeliveryTask.id == task_id, DeliveryTask.driver_id == driver.id)
        .first()
    )
    if task is None:
        raise not_found("Offer not found")
    task = dispatch_service.accept_offer(db, task, user)
    return task_to_out(task)


@router.post("/offers/{task_id}/decline")
async def decline_offer(
    task_id: int,
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    driver = get_driver_profile(user, db)
    task = (
        db.query(DeliveryTask)
        .filter(DeliveryTask.id == task_id, DeliveryTask.driver_id == driver.id)
        .first()
    )
    if task is None:
        raise not_found("Offer not found")
    task = dispatch_service.decline_offer(db, task, user)
    await manager.broadcast(
        manager.order_channel(task.order_id),
        "order.status_changed",
        {
            "order_id": task.order_id,
            "from_status": "ASSIGNED",
            "to_status": "READY",
        },
    )
    return task_to_out(task)


@router.patch("/availability")
async def set_availability(
    body: AvailabilityRequest,
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    driver = get_driver_profile(user, db)
    was_online = driver.online
    driver.online = body.online
    if body.online and not was_online:
        db.add(DriverShift(driver_id=driver.id, started_at=utcnow()))
    if not body.online and was_online:
        open_shift = (
            db.query(DriverShift)
            .filter(
                DriverShift.driver_id == driver.id,
                DriverShift.ended_at.is_(None),
            )
            .order_by(DriverShift.started_at.desc())
            .first()
        )
        if open_shift is not None:
            open_shift.ended_at = utcnow()
    db.commit()
    db.refresh(driver)
    await manager.broadcast(
        manager.DISPATCH_CHANNEL,
        "driver.online" if body.online else "driver.offline",
        {"driver_id": driver.id},
    )
    return {"driver_id": driver.id, "online": driver.online}


@router.get("/earnings")
def my_earnings(
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    """Per-delivery pay breakdown + totals, from delivered tasks."""
    driver = get_driver_profile(user, db)
    delivered = (
        db.query(DeliveryTask)
        .filter(
            DeliveryTask.driver_id == driver.id,
            DeliveryTask.status == TASK_DELIVERED,
        )
        .order_by(DeliveryTask.delivered_at.desc())
        .all()
    )
    items = []
    total_cents = 0
    for task in delivered:
        total_cents += task.offered_pay_cents
        items.append(
            {
                "task_id": task.id,
                "order_id": task.order_id,
                "order_number": task.order.order_number if task.order else None,
                "pay_cents": task.offered_pay_cents,
                "tip_cents": task.order.tip_cents if task.order else 0,
                "delivered_at": task.delivered_at,
            }
        )
    return {
        "driver_id": driver.id,
        "total_pay_cents": total_cents,
        "deliveries": len(items),
        "items": items,
    }
