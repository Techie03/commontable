"""Ledger service: the exact entry model from contract section 6.

Invariant (tested): for every order, total debits == total credits.

Standard delivery order (subtotal S, fee F, tax T, tip Tip, driver pay P,
fulfillment fee FF):
  debit  customer_charge:        S + F + T + Tip
  debit  delivery_cost_expense:  P
  credit restaurant_payable:     S + T - FF
  credit delivery_fee_revenue:   F
  credit platform_fee_revenue:   FF
  credit driver_payable:         P + Tip

Pickup order:
  debit  customer_charge:        S + T + Tip
  credit restaurant_payable:     S + T + Tip

Refunds write offsetting entries (same types, opposite direction). A full
refund reverses every original entry; a partial refund offsets the customer
charge with a refund entry. Both keep the invariant.
"""

from sqlalchemy.orm import Session

from app.models.orders import FULFILLMENT_PICKUP, Order
from app.models.payments import (
    DIRECTION_CREDIT,
    DIRECTION_DEBIT,
    ENTRY_CUSTOMER_CHARGE,
    ENTRY_DELIVERY_COST_EXPENSE,
    ENTRY_DELIVERY_FEE_REVENUE,
    ENTRY_DRIVER_PAYABLE,
    ENTRY_PLATFORM_FEE_REVENUE,
    ENTRY_REFUND,
    ENTRY_RESTAURANT_PAYABLE,
    LedgerEntry,
)


def _entry(
    db: Session,
    order_id: int,
    entry_type: str,
    direction: str,
    amount_cents: int,
    description: str,
) -> LedgerEntry:
    entry = LedgerEntry(
        order_id=order_id,
        entry_type=entry_type,
        direction=direction,
        amount_cents=amount_cents,
        currency="USD",
        description=description,
    )
    db.add(entry)
    return entry


def write_order_entries(
    db: Session,
    order: Order,
    driver_pay_cents: int,
    fulfillment_fee_cents: int,
) -> list[LedgerEntry]:
    """Write the ledger entries for a newly placed order."""
    entries: list[LedgerEntry] = []
    total = order.total_cents
    if order.fulfillment_type == FULFILLMENT_PICKUP:
        entries.append(
            _entry(db, order.id, ENTRY_CUSTOMER_CHARGE, DIRECTION_DEBIT, total,
                   "Customer charge for pickup order")
        )
        entries.append(
            _entry(db, order.id, ENTRY_RESTAURANT_PAYABLE, DIRECTION_CREDIT, total,
                   "Restaurant payable for pickup order (food, tax, and tip)")
        )
        return entries

    subtotal = order.subtotal_cents
    fee = order.delivery_fee_cents
    tax = order.tax_cents
    tip = order.tip_cents
    entries.append(
        _entry(db, order.id, ENTRY_CUSTOMER_CHARGE, DIRECTION_DEBIT, total,
               "Customer charge for delivery order")
    )
    entries.append(
        _entry(db, order.id, ENTRY_DELIVERY_COST_EXPENSE, DIRECTION_DEBIT,
               driver_pay_cents, "Driver base pay expense")
    )
    entries.append(
        _entry(db, order.id, ENTRY_RESTAURANT_PAYABLE, DIRECTION_CREDIT,
               subtotal + tax - fulfillment_fee_cents,
               "Restaurant payable (food and tax, less fulfillment fee)")
    )
    entries.append(
        _entry(db, order.id, ENTRY_DELIVERY_FEE_REVENUE, DIRECTION_CREDIT, fee,
               "Delivery fee revenue")
    )
    entries.append(
        _entry(db, order.id, ENTRY_PLATFORM_FEE_REVENUE, DIRECTION_CREDIT,
               fulfillment_fee_cents, "Restaurant fulfillment fee revenue")
    )
    entries.append(
        _entry(db, order.id, ENTRY_DRIVER_PAYABLE, DIRECTION_CREDIT,
               driver_pay_cents + tip, "Driver payable (base pay and tip)")
    )
    return entries


def write_refund_entries(db: Session, order: Order, amount_cents: int) -> list[LedgerEntry]:
    """Offsetting entries for a refund. A full refund reverses every
    original entry; a partial refund offsets the customer charge."""
    entries: list[LedgerEntry] = []
    originals = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.order_id == order.id)
        .order_by(LedgerEntry.id)
        .all()
    )
    if amount_cents >= order.total_cents:
        for original in originals:
            opposite = (
                DIRECTION_CREDIT if original.direction == DIRECTION_DEBIT
                else DIRECTION_DEBIT
            )
            entries.append(
                _entry(db, order.id, original.entry_type, opposite,
                       original.amount_cents,
                       f"Full refund reversal of entry {original.id}")
            )
    else:
        entries.append(
            _entry(db, order.id, ENTRY_REFUND, DIRECTION_DEBIT, amount_cents,
                   "Partial refund issued")
        )
        entries.append(
            _entry(db, order.id, ENTRY_CUSTOMER_CHARGE, DIRECTION_CREDIT,
                   amount_cents, "Partial refund to customer")
        )
    return entries


def order_ledger_balances(db: Session, order_id: int) -> dict:
    """Sum debits and credits for an order; the invariant is debits == credits."""
    entries = db.query(LedgerEntry).filter(LedgerEntry.order_id == order_id).all()
    debits = sum(e.amount_cents for e in entries if e.direction == DIRECTION_DEBIT)
    credits = sum(e.amount_cents for e in entries if e.direction == DIRECTION_CREDIT)
    return {"debits_cents": debits, "credits_cents": credits, "balanced": debits == credits}
