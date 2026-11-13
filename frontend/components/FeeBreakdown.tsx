// Transparent fee breakdown: subtotal, delivery fee, tax, tip, total.
// Reads from the order's immutable checkout snapshot when present.

"use client";

import { formatCents } from "@/lib/money";
import { orderFees, type FeeBreakdown as Fees, type Order } from "@/lib/types";

export default function FeeBreakdown({
  order,
  fees,
  estimate = false,
  title = "Order total",
}: {
  order?: Order;
  fees?: Fees;
  /** True when the numbers are a pre-order estimate, not the final total. */
  estimate?: boolean;
  title?: string;
}) {
  const f = fees ?? (order ? orderFees(order) : null);
  if (!f) return null;

  return (
    <dl className="app-breakdown">
      <dt className="app-breakdown-title">{title}</dt>
      <div>
        <dt>Food subtotal</dt>
        <dd>{formatCents(f.subtotal_cents, f.currency)}</dd>
      </div>
      <div>
        <dt>Delivery fee</dt>
        <dd>{formatCents(f.delivery_fee_cents, f.currency)}</dd>
      </div>
      <div>
        <dt>Tax</dt>
        <dd>{formatCents(f.tax_cents, f.currency)}</dd>
      </div>
      <div>
        <dt>Tip</dt>
        <dd>{formatCents(f.tip_cents, f.currency)}</dd>
      </div>
      <div className="app-breakdown-total">
        <dt>Total</dt>
        <dd>{formatCents(f.total_cents, f.currency)}</dd>
      </div>
      {estimate && (
        <p className="app-breakdown-note">
          Estimated fee and tax. The final breakdown is confirmed when you
          place the order.
        </p>
      )}
    </dl>
  );
}
