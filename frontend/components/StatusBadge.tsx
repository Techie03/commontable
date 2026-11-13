// Colored badge for an order status (or any short status label).

"use client";

import type { OrderStatus } from "@/lib/types";

const LABELS: Record<string, string> = {
  PLACED: "Placed",
  ACCEPTED: "Accepted",
  PREPARING: "Preparing",
  READY: "Ready",
  ASSIGNED: "Driver assigned",
  PICKED_UP: "Picked up",
  DELIVERED: "Delivered",
  COMPLETED: "Completed",
  REJECTED: "Rejected",
  CANCELLED: "Cancelled",
  REFUNDED: "Refunded",
  FAILED: "Failed",
};

const TONES: Record<string, string> = {
  PLACED: "info",
  ACCEPTED: "info",
  PREPARING: "info",
  READY: "ready",
  ASSIGNED: "ready",
  PICKED_UP: "ready",
  DELIVERED: "done",
  COMPLETED: "done",
  REJECTED: "bad",
  CANCELLED: "bad",
  REFUNDED: "bad",
  FAILED: "bad",
};

export default function StatusBadge({ status }: { status: OrderStatus | string }) {
  const tone = TONES[status] ?? "info";
  const label = LABELS[status] ?? status;
  return (
    <span className={`app-badge app-badge-${tone}`} data-status={status}>
      {label}
    </span>
  );
}
