// Order status timeline. Delivery orders follow the full chain; pickup
// orders skip dispatch and delivery steps. Timestamps come from the
// status events when the API provides them.

"use client";

import type { Order, OrderStatus, StatusEvent } from "@/lib/types";
import { orderEvents } from "@/lib/types";

const DELIVERY_STEPS: Array<{ status: OrderStatus; label: string }> = [
  { status: "PLACED", label: "Order placed" },
  { status: "ACCEPTED", label: "Accepted by restaurant" },
  { status: "PREPARING", label: "Preparing" },
  { status: "READY", label: "Ready for pickup" },
  { status: "ASSIGNED", label: "Driver assigned" },
  { status: "PICKED_UP", label: "Picked up" },
  { status: "DELIVERED", label: "Delivered" },
  { status: "COMPLETED", label: "Completed" },
];

const PICKUP_STEPS: Array<{ status: OrderStatus; label: string }> = [
  { status: "PLACED", label: "Order placed" },
  { status: "ACCEPTED", label: "Accepted by restaurant" },
  { status: "PREPARING", label: "Preparing" },
  { status: "READY", label: "Ready for pickup" },
  { status: "COMPLETED", label: "Picked up" },
];

const TERMINAL: Record<string, string> = {
  REJECTED: "Rejected by the restaurant",
  CANCELLED: "Cancelled",
  REFUNDED: "Refunded",
  FAILED: "Failed",
};

function eventTime(events: StatusEvent[], status: string): string | null {
  const ev = events.find((e) => e.to_status === status);
  const raw = ev?.created_at ?? ev?.at;
  if (!raw) return null;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString();
}

export default function OrderTimeline({ order }: { order: Order }) {
  const events = orderEvents(order);
  const steps =
    order.fulfillment_type === "pickup" ? PICKUP_STEPS : DELIVERY_STEPS;

  // Index of the current step in the chain. ACCEPTED and PREPARING are
  // adjacent: the restaurant moves to PREPARING automatically on accept,
  // so treat ACCEPTED as done once PREPARING is reached.
  const orderOf = (s: string) => steps.findIndex((st) => st.status === s);
  const currentIdx = orderOf(order.status);

  const terminal = TERMINAL[order.status];

  return (
    <ol className="app-timeline">
      {steps.map((step, idx) => {
        const done = currentIdx >= 0 && idx <= currentIdx;
        const isCurrent = idx === currentIdx;
        const time = eventTime(events, step.status);
        return (
          <li
            key={step.status}
            className={`app-timeline-step${done ? " done" : ""}${
              isCurrent ? " current" : ""
            }`}
          >
            <span className="app-timeline-dot" aria-hidden="true">
              {done ? "✓" : ""}
            </span>
            <span className="app-timeline-body">
              <span className="app-timeline-label">{step.label}</span>
              {time && <span className="app-timeline-time">{time}</span>}
            </span>
          </li>
        );
      })}
      {terminal && (
        <li className="app-timeline-step terminal">
          <span className="app-timeline-dot" aria-hidden="true">
            !
          </span>
          <span className="app-timeline-body">
            <span className="app-timeline-label">{terminal}</span>
            {eventTime(events, order.status) && (
              <span className="app-timeline-time">
                {eventTime(events, order.status)}
              </span>
            )}
          </span>
        </li>
      )}
    </ol>
  );
}
