"""Payment abstraction (spec G2) with a clearly labeled STUB provider.

No real money moves in the slice. Nothing in this module claims a payment
was processed: the stub returns status "stub_no_charge" and the response
says so in plain language. A real provider (decision D2) plugs in behind
the same interface later.
"""

from sqlalchemy.orm import Session

from app.models.orders import Order
from app.models.payments import Payment

PROVIDER_STUB = "stub"
STATUS_STUB_NO_CHARGE = "stub_no_charge"

STUB_MESSAGE = (
    "This is a test payment. No real payment is processed and no card is charged."
)


class StubPaymentProvider:
    """Test-only provider: records an intent, charges nothing."""

    name = PROVIDER_STUB

    def create_intent(self, db: Session, order: Order) -> Payment:
        payment = Payment(
            order_id=order.id,
            provider=PROVIDER_STUB,
            provider_payment_id=f"stub_{order.order_number}",
            provider_status=STATUS_STUB_NO_CHARGE,
            amount_cents=order.total_cents,
            currency="USD",
            food_processor="platform",
        )
        db.add(payment)
        db.flush()
        return payment


def get_provider(name: str = PROVIDER_STUB) -> StubPaymentProvider:
    if name != PROVIDER_STUB:
        raise ValueError(f"Payment provider '{name}' is not configured")
    return StubPaymentProvider()
