"""Dispatch service: manual assignment, override, and driver task flow.

Slice scope is manual single-order dispatch only (no batching, no OR-Tools,
no ML). Driver decline reverts the order to READY so the dispatcher can
reassign.
"""

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
from app.services import notifications
from app.services.orders import record_transition
from app.services.pricing import driver_pay_cents


def assign_driver(
    db: Session, order: Order, driver: Driver, actor: User
) -> DeliveryTask:
    """READY -> ASSIGNED with an offered delivery task."""
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
    record_transition(db, order, STATUS_ASSIGNED, actor)
    driver_name = driver.user.full_name or driver.user.email
    notifications.driver_assigned(db, order, driver_name)
    db.commit()
    db.refresh(task)
    return task


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
    """Decline reverts the order to READY so the dispatcher can reassign."""
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
