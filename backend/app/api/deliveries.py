"""Deliveries router: pickup, deliver, issue reporting (assigned driver)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_driver_profile, require_roles
from app.core.errors import not_found
from app.db.session import get_db
from app.models.drivers import DeliveryTask
from app.models.identity import ROLE_DRIVER, User
from app.schemas.orders import DeliverRequest, IssueRequest, task_to_out
from app.services import dispatch as dispatch_service
from app.services.websocket import manager

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


def _load_task(task_id: int, user: User, db: Session) -> DeliveryTask:
    driver = get_driver_profile(user, db)
    task = (
        db.query(DeliveryTask)
        .filter(DeliveryTask.id == task_id, DeliveryTask.driver_id == driver.id)
        .first()
    )
    if task is None:
        raise not_found("Delivery task not found")
    return task


@router.post("/{task_id}/pickup")
async def pickup(
    task_id: int,
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    task = _load_task(task_id, user, db)
    task = dispatch_service.confirm_pickup(db, task, user)
    await manager.broadcast(
        manager.order_channel(task.order_id),
        "order.status_changed",
        {
            "order_id": task.order_id,
            "from_status": "ASSIGNED",
            "to_status": "PICKED_UP",
        },
    )
    return task_to_out(task)


@router.post("/{task_id}/deliver")
async def deliver(
    task_id: int,
    body: DeliverRequest | None = None,
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    task = _load_task(task_id, user, db)
    task = dispatch_service.confirm_delivery(
        db, task, user, body.proof_note if body else None
    )
    # Two transitions, two events (coordination note 2). Final status COMPLETED.
    await manager.broadcast(
        manager.order_channel(task.order_id),
        "order.status_changed",
        {
            "order_id": task.order_id,
            "from_status": "PICKED_UP",
            "to_status": "DELIVERED",
        },
    )
    await manager.broadcast(
        manager.order_channel(task.order_id),
        "order.status_changed",
        {
            "order_id": task.order_id,
            "from_status": "DELIVERED",
            "to_status": "COMPLETED",
        },
    )
    return task_to_out(task)


@router.post("/{task_id}/issue", status_code=201)
def report_issue(
    task_id: int,
    body: IssueRequest,
    user: User = Depends(require_roles(ROLE_DRIVER)),
    db: Session = Depends(get_db),
):
    task = _load_task(task_id, user, db)
    ticket = dispatch_service.report_issue(db, task, user, body.description)
    return {
        "id": ticket.id,
        "order_id": ticket.order_id,
        "status": ticket.status,
        "description": ticket.description,
    }
