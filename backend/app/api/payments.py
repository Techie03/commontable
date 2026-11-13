"""Payments (stub), ledger views, and refunds."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, is_admin, require_roles
from app.core.errors import forbidden, not_found
from app.db.session import get_db
from app.models.identity import RESTAURANT_ROLES, ROLE_ADMIN, User
from app.models.orders import Order
from app.models.payments import ENTRY_RESTAURANT_PAYABLE, LedgerEntry
from app.schemas.orders import (
    LedgerEntryOut,
    PaymentIntentOut,
    PaymentIntentRequest,
    RefundOut,
    RefundRequest,
)
from app.services import orders as order_service
from app.services.payments import STUB_MESSAGE, STATUS_STUB_NO_CHARGE, get_provider

router = APIRouter(tags=["payments"])


@router.post("/payments/intent", response_model=PaymentIntentOut, status_code=201)
def create_payment_intent(
    body: PaymentIntentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """STUB provider only. No real payment is processed and no card is
    charged. The response says so plainly."""
    order = db.query(Order).filter(Order.id == body.order_id).first()
    if order is None:
        raise not_found("Order not found")
    if order.customer is None or order.customer.user_id != user.id:
        raise forbidden("Only the customer who placed this order can pay for it")
    provider = get_provider("stub")
    payment = provider.create_intent(db, order)
    order.payment_id = payment.id
    db.commit()
    return PaymentIntentOut(
        provider="stub",
        status=STATUS_STUB_NO_CHARGE,
        payment_id=payment.id,
        order_id=order.id,
        amount_cents=order.total_cents,
        currency="USD",
        message=STUB_MESSAGE,
    )


def _ledger_entry_to_out(entry: LedgerEntry) -> LedgerEntryOut:
    return LedgerEntryOut(
        id=entry.id,
        order_id=entry.order_id,
        entry_type=entry.entry_type,
        direction=entry.direction,
        amount_cents=entry.amount_cents,
        currency=entry.currency,
        description=entry.description,
        created_at=entry.created_at,
    )


@router.get("/orders/{order_id}/ledger")
def order_ledger(
    order_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Paginated ledger entries for an order. Admin sees all entries;
    restaurant staff of the order see only their own payable lines."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise not_found("Order not found")
    query = db.query(LedgerEntry).filter(LedgerEntry.order_id == order.id)
    if is_admin(user):
        pass
    elif user.has_role(*RESTAURANT_ROLES, scope_id=order.restaurant_id):
        query = query.filter(LedgerEntry.entry_type == ENTRY_RESTAURANT_PAYABLE)
    else:
        raise forbidden("You do not have access to this ledger")
    total = query.count()
    entries = (
        query.order_by(LedgerEntry.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_ledger_entry_to_out(e) for e in entries],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/orders/{order_id}/refunds", response_model=RefundOut, status_code=201)
def create_refund(
    order_id: int,
    body: RefundRequest,
    user: User = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise not_found("Order not found")
    refund = order_service.issue_refund(
        db, order, user, body.amount_cents, body.reason
    )
    return RefundOut(
        id=refund.id,
        order_id=refund.order_id,
        amount_cents=refund.amount_cents,
        reason=refund.reason,
        status=refund.status,
        created_at=refund.created_at,
    )
