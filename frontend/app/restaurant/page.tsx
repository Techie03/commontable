// Restaurant dashboard: incoming order queue (accept with prep estimate,
// reject with reason, mark ready, complete pickup) and order history.
// Live updates arrive over the restaurant WebSocket channel.

"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import StatusBadge from "@/components/StatusBadge";
import {
  acceptOrder,
  ApiError,
  completeOrder,
  createRestaurant,
  getAccessToken,
  getRestaurant,
  getRestaurantOrders,
  getRestaurantReports,
  readyOrder,
  rejectOrder,
  wsUrl,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCents } from "@/lib/money";
import {
  orderDisplayName,
  orderFees,
  orderLineItems,
  type Order,
  type Restaurant,
} from "@/lib/types";

const QUEUE_STATUSES = ["PLACED", "ACCEPTED", "PREPARING", "READY"];
const MANUAL_ID_KEY = "commontable.restaurant_manual_id";

export default function RestaurantPage() {
  return (
    <AppShell>
      <RestaurantDashboard />
    </AppShell>
  );
}

function RestaurantDashboard() {
  const { user, ready, restaurantId, refreshUser } = useAuth();
  const [manualId, setManualId] = useState("");
  const [manualInput, setManualInput] = useState("");
  const [createName, setCreateName] = useState("");
  const [createPhone, setCreatePhone] = useState("");
  const [createEmail, setCreateEmail] = useState("");
  const [createWebsite, setCreateWebsite] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createOwnerName, setCreateOwnerName] = useState("");
  const [createAddress, setCreateAddress] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [reports, setReports] = useState<{
    orders_today?: number;
    total_orders?: number;
    revenue_cents?: number;
    avg_prep_minutes?: number | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [live, setLive] = useState(false);
  const [prepMinutes, setPrepMinutes] = useState<Record<string, string>>({});
  const [rejectReason, setRejectReason] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const activeId = restaurantId ?? manualId;

  useEffect(() => {
    try {
      const saved = window.sessionStorage.getItem(MANUAL_ID_KEY);
      if (saved) {
        setManualId(saved);
        setManualInput(saved);
      }
    } catch {
      // ignore
    }
  }, []);

  const load = useCallback(async () => {
    if (!activeId) {
      setLoading(false);
      return;
    }
    setError(null);
    try {
      const [r, list] = await Promise.all([
        getRestaurant(activeId),
        getRestaurantOrders(activeId),
      ]);
      setRestaurant(r);
      setOrders(list);
      getRestaurantReports(activeId)
        .then(setReports)
        .catch(() => undefined);
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("Could not load the restaurant dashboard.");
    } finally {
      setLoading(false);
    }
  }, [activeId]);

  useEffect(() => {
    if (!ready) return;
    load();
  }, [ready, load]);

  // Live updates: refresh the queue when an order is placed or cancelled.
  useEffect(() => {
    const token = getAccessToken();
    if (!token || !activeId || offline) return;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(
        `${wsUrl(`/api/v1/ws/restaurant/${activeId}`)}?token=${encodeURIComponent(token)}`
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
        const msg = JSON.parse(ev.data as string) as { type?: string };
        if (msg.type === "order.placed" || msg.type === "order.cancelled") {
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
  }, [activeId, offline, load]);

  const runAction = async (orderId: string, fn: () => Promise<unknown>) => {
    setBusyId(orderId);
    setError(null);
    try {
      await fn();
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("That action did not go through. Please try again.");
    } finally {
      setBusyId(null);
    }
  };

  const saveManualId = () => {
    const id = manualInput.trim();
    setManualId(id);
    try {
      if (id) window.sessionStorage.setItem(MANUAL_ID_KEY, id);
      else window.sessionStorage.removeItem(MANUAL_ID_KEY);
    } catch {
      // ignore
    }
  };

  // New owner onboarding: create the restaurant instead of asking for an
  // id the owner cannot know yet. The backend scopes the creator to it;
  // the id is also kept locally so the dashboard opens at once, and the
  // session refresh makes the scope stick for later visits.
  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    const name = createName.trim();
    if (!name) {
      setCreateError("Give your restaurant a name.");
      return;
    }
    const ownerName = createOwnerName.trim();
    const phone = createPhone.trim();
    const address = createAddress.trim();
    if (!ownerName || !phone || !address) {
      setCreateError(
        "Owner name, business phone, and business address are required. We verify every restaurant before it can take orders."
      );
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createRestaurant({
        name,
        phone,
        email: createEmail.trim() || undefined,
        website: createWebsite.trim() || undefined,
        description: createDescription.trim() || undefined,
        owner_name: ownerName,
        business_address: address,
      });
      const id = String(created.id);
      setManualId(id);
      try {
        window.sessionStorage.setItem(MANUAL_ID_KEY, id);
      } catch {
        // ignore
      }
      refreshUser().catch(() => undefined);
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setCreateError(err.message);
      else setCreateError("Could not create the restaurant. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  if (offline) {
    return <ApiOffline onRetry={() => { setOffline(false); setLoading(true); load(); }} />;
  }

  if (!ready || loading) {
    return <p>Loading the restaurant dashboard…</p>;
  }

  if (!user) {
    return (
      <div>
        <h1>Restaurant dashboard</h1>
        <p>
          <Link href="/login">Sign in</Link> with a restaurant account to
          manage orders and menus.
        </p>
      </div>
    );
  }

  if (!activeId) {
    return (
      <div>
        <h1>Restaurant dashboard</h1>
        <p>
          No restaurant is linked to your account yet. Set up your
          restaurant below and its dashboard opens right away.
        </p>
        <section className="app-card" aria-label="Set up your restaurant">
          <h2>Set up your restaurant</h2>
          <p className="app-muted">
            Your restaurant is created as pending. You can set up your menu
            right away. Before it can take orders, we verify it is a real
            operating business — owner, business phone, and business address
            are checked against a public listing.
          </p>
          <form onSubmit={handleCreate}>
            <label className="app-field">
              <span>Restaurant name</span>
              <input
                className="app-input"
                type="text"
                required
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="Your restaurant's name"
              />
            </label>
            <label className="app-field">
              <span>Owner name</span>
              <input
                className="app-input"
                type="text"
                required
                value={createOwnerName}
                onChange={(e) => setCreateOwnerName(e.target.value)}
                placeholder="The owner's full name"
              />
            </label>
            <label className="app-field">
              <span>Business phone</span>
              <input
                className="app-input"
                type="tel"
                required
                value={createPhone}
                onChange={(e) => setCreatePhone(e.target.value)}
                placeholder="(940) 555-0100"
              />
            </label>
            <label className="app-field">
              <span>Business address</span>
              <input
                className="app-input"
                type="text"
                required
                value={createAddress}
                onChange={(e) => setCreateAddress(e.target.value)}
                placeholder="Street, city, state, ZIP"
              />
            </label>
            <label className="app-field">
              <span>Email (optional)</span>
              <input
                className="app-input"
                type="email"
                value={createEmail}
                onChange={(e) => setCreateEmail(e.target.value)}
                placeholder="hello@yourrestaurant.com"
              />
            </label>
            <label className="app-field">
              <span>Website or listing (optional — helps verification)</span>
              <input
                className="app-input"
                type="url"
                value={createWebsite}
                onChange={(e) => setCreateWebsite(e.target.value)}
                placeholder="https://yourrestaurant.com"
              />
            </label>
            <label className="app-field">
              <span>About your restaurant (optional)</span>
              <input
                className="app-input"
                type="text"
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
                placeholder="A line about the food you serve"
              />
            </label>
            {createError && (
              <p className="app-error" role="alert">
                {createError}
              </p>
            )}
            <button type="submit" className="app-btn" disabled={creating}>
              {creating ? "Creating…" : "Create restaurant"}
            </button>
          </form>
        </section>
        <section aria-label="Open an existing restaurant">
          <h2>Already on CommonTable?</h2>
          <p>
            If your restaurant already exists, enter its id to open its
            dashboard.
          </p>
          <div className="app-inline-form">
            <input
              className="app-input"
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="Restaurant id"
            />
            <button type="button" className="app-btn" onClick={saveManualId}>
              Open dashboard
            </button>
          </div>
        </section>
      </div>
    );
  }

  const queue = orders.filter((o) => QUEUE_STATUSES.includes(o.status));
  const history = orders.filter((o) => !QUEUE_STATUSES.includes(o.status));

  return (
    <div>
      <div className="app-page-head">
        <h1>{restaurant?.name ?? "Restaurant dashboard"}</h1>
        {restaurant?.status === "demo" && (
          <span className="app-tag">Demo restaurant</span>
        )}
      </div>
      <p className="app-live-indicator" role="status">
        {live
          ? "Live updates connected. New orders appear here as they arrive."
          : "Live updates are not connected right now. Refresh to check for new orders."}
      </p>
      <p className="app-lede">
        <Link href="/restaurant/menu">Manage the menu</Link>
        {" · "}
        <Link href="/restaurant/direct2door">Record a Direct2Door order</Link>
      </p>

      {reports && (
        <div className="app-stat-strip">
          <div className="app-stat">
            <span className="app-stat-number">{reports.orders_today ?? 0}</span>
            <span className="app-stat-label">Orders today</span>
          </div>
          <div className="app-stat">
            <span className="app-stat-number">{reports.total_orders ?? 0}</span>
            <span className="app-stat-label">Total orders</span>
          </div>
          <div className="app-stat">
            <span className="app-stat-number">
              {formatCents(reports.revenue_cents)}
            </span>
            <span className="app-stat-label">Revenue</span>
          </div>
          <div className="app-stat">
            <span className="app-stat-number">
              {reports.avg_prep_minutes != null
                ? `${reports.avg_prep_minutes} min`
                : "—"}
            </span>
            <span className="app-stat-label">Average prep time</span>
          </div>
        </div>
      )}

      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      <section aria-label="Incoming orders">
        <h2>Incoming orders</h2>
        {queue.length === 0 ? (
          <p>No orders are waiting right now.</p>
        ) : (
          <ul className="app-list">
            {queue.map((o) => (
              <li key={o.id} className="app-list-row app-order-row">
                <div>
                  <span className="app-list-title">
                    {orderDisplayName(o)} · <StatusBadge status={o.status} />
                  </span>
                  <span className="app-list-sub">
                    {o.fulfillment_type === "pickup" ? "Pickup" : "Standard delivery"}
                    {o.channel === "direct2door" ? " · Direct2Door" : ""}
                    {o.customer_name ? ` · ${o.customer_name}` : ""}
                    {o.created_at
                      ? ` · ${new Date(o.created_at).toLocaleString()}`
                      : ""}
                  </span>
                  <ul className="app-item-lines">
                    {orderLineItems(o).map((item) => (
                      <li key={item.key}>
                        {item.quantity} × {item.name}
                        {item.modifiers.length > 0
                          ? ` (${item.modifiers.join(", ")})`
                          : ""}
                      </li>
                    ))}
                  </ul>
                  <span className="app-list-sub">
                    Total {formatCents(orderFees(o).total_cents)}
                    {o.prep_minutes != null
                      ? ` · Prep estimate ${o.prep_minutes} min`
                      : ""}
                  </span>
                </div>
                <div className="app-actions">
                  {o.status === "PLACED" && (
                    <>
                      <label className="app-field app-field-inline">
                        <span className="app-visually-hidden">
                          Prep estimate in minutes
                        </span>
                        <input
                          className="app-input"
                          inputMode="numeric"
                          placeholder="Prep min"
                          value={prepMinutes[o.id] ?? "20"}
                          onChange={(e) =>
                            setPrepMinutes({ ...prepMinutes, [o.id]: e.target.value })
                          }
                        />
                      </label>
                      <button
                        type="button"
                        className="app-btn app-btn-small"
                        disabled={busyId === o.id}
                        onClick={() =>
                          runAction(o.id, () =>
                            acceptOrder(
                              o.id,
                              Number.parseInt(prepMinutes[o.id] ?? "20", 10) || 20
                            )
                          )
                        }
                      >
                        Accept
                      </button>
                      <label className="app-field app-field-inline">
                        <span className="app-visually-hidden">Reject reason</span>
                        <input
                          className="app-input"
                          placeholder="Reason to reject"
                          value={rejectReason[o.id] ?? ""}
                          onChange={(e) =>
                            setRejectReason({ ...rejectReason, [o.id]: e.target.value })
                          }
                        />
                      </label>
                      <button
                        type="button"
                        className="app-btn app-btn-small app-btn-danger"
                        disabled={busyId === o.id}
                        onClick={() =>
                          runAction(o.id, () =>
                            rejectOrder(o.id, rejectReason[o.id] || "Not available")
                          )
                        }
                      >
                        Reject
                      </button>
                    </>
                  )}
                  {(o.status === "ACCEPTED" || o.status === "PREPARING") && (
                    <button
                      type="button"
                      className="app-btn app-btn-small"
                      disabled={busyId === o.id}
                      onClick={() => runAction(o.id, () => readyOrder(o.id))}
                    >
                      Mark ready
                    </button>
                  )}
                  {o.status === "READY" && o.fulfillment_type === "pickup" && (
                    <button
                      type="button"
                      className="app-btn app-btn-small"
                      disabled={busyId === o.id}
                      onClick={() => runAction(o.id, () => completeOrder(o.id))}
                    >
                      Complete pickup
                    </button>
                  )}
                  {o.status === "READY" && o.fulfillment_type !== "pickup" && (
                    <span className="app-muted">
                      Waiting for a driver to be assigned.
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Order history">
        <h2>Order history</h2>
        {history.length === 0 ? (
          <p>No completed or closed orders yet.</p>
        ) : (
          <ul className="app-list">
            {history.map((o) => (
              <li key={o.id} className="app-list-row">
                <span>
                  <strong>{orderDisplayName(o)}</strong>
                  <span className="app-list-sub">
                    {o.fulfillment_type === "pickup" ? "Pickup" : "Standard delivery"}
                    {o.created_at
                      ? ` · ${new Date(o.created_at).toLocaleString()}`
                      : ""}
                  </span>
                </span>
                <span className="app-list-right">
                  <StatusBadge status={o.status} />
                  <strong>{formatCents(orderFees(o).total_cents)}</strong>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
