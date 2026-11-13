"""Notifications router: own notifications, mark read."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.errors import not_found
from app.db.session import get_db
from app.models.identity import User
from app.models.misc import Notification
from app.schemas.orders import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        type=n.type,
        title=n.title,
        body=n.body,
        order_id=n.order_id,
        read=n.read,
        created_at=n.created_at,
    )


@router.get("")
def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read.is_(False))
        .count()
    )
    return {
        "items": [_to_out(n) for n in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "unread_count": unread,
    }


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if notif is None:
        raise not_found("Notification not found")
    notif.read = True
    db.commit()
    db.refresh(notif)
    return _to_out(notif)


@router.post("/read-all")
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read.is_(False))
        .update({"read": True})
    )
    db.commit()
    return {"marked_read": updated}
