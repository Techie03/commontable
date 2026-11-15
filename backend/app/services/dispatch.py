"""Dispatch service: automatic assignment, manual override, driver task flow.

Assignment is automatic: when a delivery order becomes ready, it is
offered to the best available driver (approved, online, no active task,
has not declined this order), fairest first — the driver who has waited
longest since their last task. When no driver is available the order
stays READY and waits; the queue runs again whenever a driver comes
online, declines an offer, or finishes a delivery. A dispatcher can
still assign or override by hand; the manual endpoints stay as the
override path. No batching, no OR-Tools, no ML.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, not_found
from app.models.common import utcnow
from app.models.drivers import (
    ONBOARDING_APPROVED,
    TASK_ACCEPTED,
    TASK_DECLINED,
    TASK_DELIVERED,
    TASK_OFFERED,
    TASK_PICKED_UP,
    TASK_WITHDRAWN,
    DeliveryTask,
    Driver,
)
from app.models.identity import User
from app.models.misc import SupportTicket
from app.models.orders import (
    FULFILLMENT_PICKUP,
    STATUS_ASSIGNED,
    STATUS_COMPLETED,
    STATUS_DELIVERED,
    STATUS_PICKED_UP,
    STATUS_READY,
    Order,
    StatusEvent,
)
from app.schemas.orders import task_to_out
from app.services import notifications
from app.services.orders import record_transition
from app.services.pricing import driver_pay_cents
from app.services.websocket import manager

# A driver with a task in one of these states is busy and gets no new offer.
ACTIVE_TASK_STATUSES = [TASK_OFFERED, TASK_ACCEPTED, TASK_PICKED_UP]


def assign_driver(
    db: Session,
    order: Order,
    driver: Driver,
    actor: User | None = None,
    reason: str | None = None,
) -> DeliveryTask:
    """READY -> ASSIGNED with an offered delivery task. Actor is None for
    automatic assignment (a system transition)."""
    if order.fulfillment_type == FULFILLMENT_PICKUP:
        raise bad_request(
            "Pickup orders never go through dispatch; the restaurant completes them",
            code="pickup_not_dispatchable",
        )
    if order.status != STATUS_READY:
        raise bad_request(
            f"Only a ready order can be assigned a driver (now {order.status})"
        )
    if driver.onboarding_status != ONBOARDING_APPROVED:
        raise bad_request("That driver is not approved yet")
    zone_id = None
    if order.restaurant_location and order.restaurant_location.service_zone_ids:
        zone_id = order.restaurant_location.service_zone_ids[0]
    pay = driver_pay_cents(db, zone_id) + (order.tip_cents or 0)
    task = DeliveryTask(
        order_id=order.id,
        driver_id=driver.id,
        status=TASK_OFFERED,
        offered_pay_cents=pay,
    )
    db.add(task)
    record_transition(db, order, STATUS_ASSIGNED, actor, reason=reason)
    driver_name = driver.user.full_name or driver.user.email
    notifications.driver_assigned(db, order, driver_name)
    db.commit()
    db.refresh(task)
    return task


def pick_driver(db: Session, order: Order) -> Driver | None:
    """Best available driver for an order, or None when nobody can take
    it: approved, online, no active task, and has not declined this
    order. Fairest first — the driver whose last task is oldest (a
    driver who never had a task comes first), ties by driver id."""
    busy_ids = (
        select(DeliveryTask.driver_id)
        .where(DeliveryTask.status.in_(ACTIVE_TASK_STATUSES))
        .distinct()
    )
    declined_ids = (
        select(DeliveryTask.driver_id)
        .where(
            DeliveryTask.order_id == order.id,
            DeliveryTask.status == TASK_DECLINED,
        )
        .distinct()
    )
    candidates = (
        db.query(Driver)
        .filter(
            Driver.onboarding_status == ONBOARDING_APPROVED,
            Driver.online.is_(True),
            ~Driver.id.in_(busy_ids),
            ~Driver.id.in_(declined_ids),
        )
        .all()
    )
    if not candidates:
        return None
    last_task_ids = dict(
        db.query(DeliveryTask.driver_id, func.max(DeliveryTask.id))
        .filter(DeliveryTask.driver_id.in_([d.id for d in candidates]))
        .group_by(DeliveryTask.driver_id)
        .all()
    )

    def fairness_key(driver: Driver) -> tuple[bool, int, int]:
        last = last_task_ids.get(driver.id)
        # Never tasked first, then the oldest last task, then lowest id.
        return (last is not None, last or 0, driver.id)

    candidates.sort(key=fairness_key)
    return candidates[0]


def auto_assign_order(
    db: Session, order: Order, actor: User | None = None
) -> DeliveryTask | None:
    """Offer a READY delivery order to the best available driver.
    Returns the task, or None when no driver can take it — the order
    stays READY and waits for the next trigger."""
    if order.status != STATUS_READY:
        return None
    if order.fulfillment_type == FULFILLMENT_PICKUP:
        return None
    driver = pick_driver(db, order)
    if driver is None:
        return None
    return assign_driver(db, order, driver, actor, reason="Auto-assigned")


def auto_assign_queue(
    db: Session, actor: User | None = None
) -> list[DeliveryTask]:
    """Offer every waiting READY delivery order, oldest first, to the
    next available driver, until drivers or orders run out. Runs when a
    driver comes online or finishes a delivery."""
    waiting = (
        db.query(Order)
        .filter(
            Order.status == STATUS_READY,
            Order.fulfillment_type != FULFILLMENT_PICKUP,
        )
        .order_by(Order.ready_at, Order.id)
        .all()
    )
    tasks: list[DeliveryTask] = []
    for order in waiting:
        task = auto_assign_order(db, order, actor)
        if task is None:
            break
        tasks.append(task)
    return tasks


async def announce_assignment(
    task: DeliveryTask, *, from_status: str | None = None
) -> None:
    """Broadcast an assignment (manual or automatic): the offer to the
    driver, the assignment to the order channel, and the status change
    when the order moved (READY -> ASSIGNED)."""
    order = task.order
    driver = task.driver
    task_out = task_to_out(task)
    await manager.broadcast(
        manager.driver_channel(task.driver_id),
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
    if from_status is not None:
        await manager.broadcast(
            manager.order_channel(order.id),
            "order.status_changed",
            {
                "order_id": order.id,
                "from_status": from_status,
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


def override_assignment(
    db: Session, order: Order, new_driver: Driver, actor: User, reason: str
) -> DeliveryTask:
    """Withdraw the current offer/task and create a new offer for another
    driver. The order stays ASSIGNED; the override is audited."""
    if order.status != STATUS_ASSIGNED:
        raise bad_request(
            f"Only an assigned order can be overridden (now {order.status})"
        )
    if new_driver.onboarding_status != ONBOARDING_APPROVED:
        raise bad_request("That driver is not approved yet")
    current = (
        db.query(DeliveryTask)
        .filter(
            DeliveryTask.order_id == order.id,
            DeliveryTask.status.in_([TASK_OFFERED, TASK_ACCEPTED]),
        )
        .order_by(DeliveryTask.id.desc())
        .first()
    )
    if current is None:
        raise not_found("No active delivery task to override")
    current.status = TASK_WITHDRAWN
    zone_id = None
    if order.restaurant_location and order.restaurant_location.service_zone_ids:
        zone_id = order.restaurant_location.service_zone_ids[0]
    pay = driver_pay_cents(db, zone_id) + (order.tip_cents or 0)
    task = DeliveryTask(
        order_id=order.id,
        driver_id=new_driver.id,
        status=TASK_OFFERED,
        offered_pay_cents=pay,
    )
    db.add(task)
    # Audit the override without changing the order status (it stays ASSIGNED).
    db.add(
        StatusEvent(
            order_id=order.id,
            from_status=STATUS_ASSIGNED,
            to_status=STATUS_ASSIGNED,
            actor_user_id=actor.id,
            reason=f"Override: {reason}",
        )
    )
    db.commit()
    db.refresh(task)
    return task


def accept_offer(db: Session, task: DeliveryTask, actor: User) -> DeliveryTask:
    if task.status != TASK_OFFERED:
        raise bad_request(f"Only a pending offer can be accepted (now {task.status})")
    task.status = TASK_ACCEPTED
    task.accepted_at = utcnow()
    db.commit()
    db.refresh(task)
    return task


def decline_offer(db: Session, task: DeliveryTask, actor: User) -> DeliveryTask:
    """Decline reverts the order to READY; the caller re-runs auto-assign
    so the next available driver is offered the order."""
    if task.status != TASK_OFFERED:
        raise bad_request(f"Only a pending offer can be declined (now {task.status})")
    task.status = TASK_DECLINED
    order = task.order
    if order.status == STATUS_ASSIGNED:
        record_transition(db, order, STATUS_READY, actor, reason="Driver declined")
    db.commit()
    db.refresh(task)
    return task


def confirm_pickup(db: Session, task: DeliveryTask, actor: User) -> DeliveryTask:
    if task.status != TASK_ACCEPTED:
        raise bad_request(f"Only an accepted task can be picked up (now {task.status})")
    task.status = TASK_PICKED_UP
    task.picked_up_at = utcnow()
    record_transition(db, task.order, STATUS_PICKED_UP, actor)
    notifications.order_picked_up(db, task.order)
    db.commit()
    db.refresh(task)
    return task


def confirm_delivery(
    db: Session, task: DeliveryTask, actor: User, proof_note: str | None
) -> DeliveryTask:
    """DELIVERED, then COMPLETED by the system (contract section 3)."""
    if task.status != TASK_PICKED_UP:
        raise bad_request(f"Only a picked up task can be delivered (now {task.status})")
    task.status = TASK_DELIVERED
    task.delivered_at = utcnow()
    task.proof_note = proof_note
    order = task.order
    record_transition(db, order, STATUS_DELIVERED, actor)
    order.delivered_at = utcnow()
    notifications.order_delivered(db, order)
    record_transition(db, order, STATUS_COMPLETED, None)
    order.completed_at = utcnow()
    db.commit()
    db.refresh(task)
    return task


def report_issue(
    db: Session, task: DeliveryTask, actor: User, description: str
) -> SupportTicket:
    ticket = SupportTicket(
        order_id=task.order_id,
        reporter_user_id=actor.id,
        type="other",
        status="open",
        description=description,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket
