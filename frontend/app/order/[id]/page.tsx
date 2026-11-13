// Live order tracking: status timeline updated in realtime over
// WebSocket, plus the immutable checkout snapshot and fee breakdown.

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import FeeBreakdown from "@/components/FeeBreakdown";
import OrderTimeline from "@/components/OrderTimeline";
import StatusBadge from "@/components/StatusBadge";
import {
  ApiError,
  cancelOrder,
  getAccessToken,
  getOrder,
  getOrderEvents,
  rateOrder,
  wsUrl,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCents } from "@/lib/money";
import {
  addressLine,
  orderDisplayName,
  orderEvents,
  type Order,
  type StatusEvent,
} from "@/lib/types";

const CANCELLABLE = ["PLACED", "ACCEPTED", "PREPARING"];

export default function OrderDetailPage({ params }: { params: { id: string } }) {
  return (
    <AppShell>
      <OrderDetail id={params.id} />
    </AppShell>
  );
}

function OrderDetail({ id }: { id: string }) {
  const { user, ready } = useAuth();
  const [order, setOrder] = useState<Order | null>(null);
  const [events, setEvents] = useState<StatusEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [live, setLive] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [rating, setRating] = useState(5);
  const [ratingComment, setRatingComment] = useState("");
  const [ratingSent, setRatingSent] = useState(false);
  const [ratingBusy, setRatingBusy] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [o, evts] = await Promise.all([
        getOrder(id),
        getOrderEvents(id).catch(() => [] as StatusEvent[]),
      ]);
      setOrder(o);
      const merged = orderEvents(o).length > 0 ? orderEvents(o) : evts;
      setEvents(merged);
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) {
        setOffline(true);
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Could not load this order.");
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Live updates over the order channel. The socket only triggers a
  // refetch; the API response is the source of truth.
  useEffect(() => {
    const token = getAccessToken();
    if (!token || offline) return;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(
        `${wsUrl(`/api/v1/ws/orders/${id}`)}?token=${encodeURIComponent(token)}`
      );
    } catch {
      return;
    }
    wsRef.current = ws;
    ws.onopen = () => setLive(true);
    ws.onclose = () => setLive(false);
    ws.onerror = () => setLive(false);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as {
          type?: string;
          data?: Record<string, unknown>;
        };
        if (
          msg.type === "order.status_changed" ||
          msg.type === "order.driver_assigned" ||
          msg.type === "order.eta_updated"
        ) {
          load();
        }
      } catch {
        // Ignore malformed frames.
      }
    };
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [id, offline, load]);

  const handleCancel = async () => {
    setCancelling(true);
    setError(null);
    try {
      const updated = await cancelOrder(id, cancelReason || "Cancelled by customer");
      setOrder(updated);
      setCancelReason("");
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("Could not cancel the order.");
    } finally {
      setCancelling(false);
    }
  };

  const handleRate = async () => {
    setRatingBusy(true);
    setError(null);
    try {
      await rateOrder(id, rating, ratingComment || undefined);
      setRatingSent(true);
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("Could not send the rating.");
    } finally {
      setRatingBusy(false);
    }
  };

  if (offline) {
    return <ApiOffline onRetry={() => { setOffline(false); setLoading(true); load(); }} />;
  }

  if (loading) {
    return <p>Loading your order…</p>;
  }

  if (error && !order) {
    return (
      <div>
        <p className="app-error" role="alert">{error}</p>
        <p><Link href="/orders">Back to my orders</Link></p>
      </div>
    );
  }

  if (!order) {
    return <p>Order not found.</p>;
  }

  const isCustomer = user?.id === order.customer_id;
  const canCancel = isCustomer && CANCELLABLE.includes(order.status);
  const canRate =
    isCustomer && (order.status === "DELIVERED" || order.status === "COMPLETED");
  const withEvents: Order = { ...order, status_events: events };

  return (
    <div className="app-order-detail">
      <p className="app-back">
        <Link href="/orders">← My orders</Link>
      </p>
      <div className="app-page-head">
        <h1>{orderDisplayName(order)}</h1>
        <StatusBadge status={order.status} />
      </div>
      <p className="app-lede">
        {order.restaurant_name ?? "Restaurant"} ·{" "}
        {order.fulfillment_type === "pickup" ? "Pickup" : "Standard delivery"}
        {order.channel === "direct2door" ? " · Direct2Door" : ""}
      </p>
      <p className="app-live-indicator" role="status">
        {live
          ? "Live updates connected. This page refreshes as your order moves."
          : "Live updates are not connected right now. Refresh to check the latest status."}
      </p>

      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      <div className="app-detail-grid">
        <section className="app-card" aria-label="Order status">
          <h2>Status</h2>
          <OrderTimeline order={withEvents} />
          {order.prep_minutes != null && (
            <p>Estimated prep time: {order.prep_minutes} minutes.</p>
          )}
          {order.driver_name && <p>Driver: {order.driver_name}</p>}
          {order.delivery_address && (
            <p>
              Deliver to: {addressLine(order.delivery_address)}
            </p>
          )}
          {order.created_at && (
            <p className="app-muted">
              Placed {new Date(order.created_at).toLocaleString()}
            </p>
          )}
        </section>

        <section className="app-card" aria-label="Order total">
          <h2>Your order</h2>
          <ul className="app-list">
            {order.items.map((item, idx) => (
              <li key={`${item.menu_item_id}-${idx}`} className="app-list-row">
                <span>
                  <strong>
                    {item.quantity} × {item.name ?? "Menu item"}
                  </strong>
                  {item.modifiers && item.modifiers.length > 0 && (
                    <span className="app-list-sub">
                      {item.modifiers.map((m) => m.name).join(", ")}
                    </span>
                  )}
                </span>
                <span>
                  {formatCents(
                    item.total_cents ??
                      (item.unit_price_cents ?? item.price_cents ?? 0) *
                        item.quantity
                  )}
                </span>
              </li>
            ))}
          </ul>
          <FeeBreakdown order={order} title="Checkout total" />
          <p className="app-muted">
            This total was fixed when you placed the order and does not change.
          </p>
          <p className="app-stub-note">
            Demo checkout: no card was charged and no real money moved.
          </p>
        </section>
      </div>

      {canCancel && (
        <section className="app-card" aria-label="Cancel order">
          <h2>Cancel this order</h2>
          <p>
            You can cancel while the restaurant is still preparing it.
          </p>
          <label className="app-field">
            <span>Reason (optional)</span>
            <input
              className="app-input"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="Changed my mind"
            />
          </label>
          <button
            type="button"
            className="app-btn app-btn-danger"
            onClick={handleCancel}
            disabled={cancelling}
          >
            {cancelling ? "Cancelling…" : "Cancel order"}
          </button>
        </section>
      )}

      {canRate && (
        <section className="app-card" aria-label="Rate this order">
          <h2>How was it?</h2>
          {ratingSent ? (
            <p>Thanks for the rating.</p>
          ) : (
            <>
              <label className="app-field">
                <span>Rating (1 to 5)</span>
                <select
                  className="app-input"
                  value={rating}
                  onChange={(e) => setRating(Number(e.target.value))}
                >
                  {[5, 4, 3, 2, 1].map((n) => (
                    <option key={n} value={n}>
                      {n} star{n === 1 ? "" : "s"}
                    </option>
                  ))}
                </select>
              </label>
              <label className="app-field">
                <span>Comment (optional)</span>
                <textarea
                  className="app-input"
                  value={ratingComment}
                  onChange={(e) => setRatingComment(e.target.value)}
                  rows={3}
                />
              </label>
              <button
                type="button"
                className="app-btn"
                onClick={handleRate}
                disabled={ratingBusy}
              >
                {ratingBusy ? "Sending…" : "Send rating"}
              </button>
            </>
          )}
        </section>
      )}

      {ready && !user && (
        <p className="app-notice">
          <Link href="/login">Sign in</Link> to see the live status of your
          orders.
        </p>
      )}
    </div>
  );
}
