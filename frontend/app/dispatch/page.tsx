// Dispatch board: active orders, ready signals, online drivers.
// Manual assignment and override only (no batching in the slice).

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import StatusBadge from "@/components/StatusBadge";
import {
  ApiError,
  assignOrder,
  getAccessToken,
  getDispatchBoard,
  overrideAssignment,
  wsUrl,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { addressLine, shortId, type DispatchBoard, type Order } from "@/lib/types";

export default function DispatchPage() {
  return (
    <AppShell>
      <DispatchBoardView />
    </AppShell>
  );
}

function DispatchBoardView() {
  const { user, ready } = useAuth();
  const [board, setBoard] = useState<DispatchBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [live, setLive] = useState(false);
  const [selectedDriver, setSelectedDriver] = useState<Record<string, string>>({});
  const [overrideReason, setOverrideReason] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setBoard(await getDispatchBoard());
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("Could not load the dispatch board.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      setLoading(false);
      return;
    }
    load();
  }, [ready, user, load]);

  // Live board updates: refresh when orders move or drivers change state.
  useEffect(() => {
    const token = getAccessToken();
    if (!token || offline) return;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(
        `${wsUrl("/api/v1/ws/dispatch")}?token=${encodeURIComponent(token)}`
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
        if (
          msg.type === "order.placed" ||
          msg.type === "order.ready" ||
          msg.type === "driver.online" ||
          msg.type === "driver.offline"
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
  }, [offline, load]);

  const runAssign = async (orderId: string, isOverride: boolean) => {
    const driverId = selectedDriver[orderId];
    if (!driverId) {
      setError("Choose a driver first.");
      return;
    }
    if (isOverride && !overrideReason[orderId]?.trim()) {
      setError("Give a reason for the override.");
      return;
    }
    setBusyId(orderId);
    setError(null);
    try {
      if (isOverride) {
        await overrideAssignment(orderId, driverId, overrideReason[orderId].trim());
      } else {
        await assignOrder(orderId, driverId);
      }
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("The assignment did not go through. Please try again.");
    } finally {
      setBusyId(null);
    }
  };

  if (offline) {
    return <ApiOffline onRetry={() => { setOffline(false); setLoading(true); load(); }} />;
  }

  if (!ready || loading) {
    return <p>Loading the dispatch board…</p>;
  }

  if (!user) {
    return (
      <div>
        <h1>Dispatch</h1>
        <p>
          <Link href="/login">Sign in</Link> with a dispatcher or admin
          account to open the board.
        </p>
      </div>
    );
  }

  const activeOrders: Order[] = board?.active_orders ?? [];
  const readyOrders: Order[] =
    board?.ready_orders ?? activeOrders.filter((o) => o.status === "READY");
  const onlineDrivers = board?.online_drivers ?? [];

  return (
    <div>
      <h1>Dispatch board</h1>
      <p className="app-live-indicator" role="status">
        {live
          ? "Live updates connected. The board refreshes as orders and drivers change."
          : "Live updates are not connected right now. Refresh to see the latest board."}
      </p>
      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      <section aria-label="Ready orders">
        <h2>Ready for a driver ({readyOrders.length})</h2>
        {readyOrders.length === 0 ? (
          <p>No orders are waiting for a driver right now.</p>
        ) : (
          <ul className="app-list">
            {readyOrders.map((o) => (
              <li key={o.id} className="app-list-row app-order-row">
                <div>
                  <span className="app-list-title">
                    Order {shortId(o.id)} · <StatusBadge status={o.status} />
                  </span>
                  <span className="app-list-sub">
                    {o.restaurant_name ?? "Restaurant"}
                    {o.delivery_address
                      ? ` → ${addressLine(o.delivery_address)}`
                      : ""}
                  </span>
                  <span className="app-list-sub">
                    {o.items
                      .map((i) => `${i.quantity} × ${i.name ?? "Menu item"}`)
                      .join(", ")}
                  </span>
                </div>
                <div className="app-actions">
                  <label className="app-field app-field-inline">
                    <span className="app-visually-hidden">Choose a driver</span>
                    <select
                      className="app-input"
                      value={selectedDriver[o.id] ?? ""}
                      onChange={(e) =>
                        setSelectedDriver({ ...selectedDriver, [o.id]: e.target.value })
                      }
                    >
                      <option value="">Choose a driver…</option>
                      {onlineDrivers.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.full_name ?? d.name ?? d.email ?? d.id}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="app-btn app-btn-small"
                    disabled={busyId === o.id || onlineDrivers.length === 0}
                    onClick={() => runAssign(o.id, false)}
                  >
                    Assign
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Active orders">
        <h2>Active orders</h2>
        {activeOrders.length === 0 ? (
          <p>No active orders right now.</p>
        ) : (
          <ul className="app-list">
            {activeOrders.map((o) => (
              <li key={o.id} className="app-list-row app-order-row">
                <div>
                  <span className="app-list-title">
                    Order {shortId(o.id)} · <StatusBadge status={o.status} />
                  </span>
                  <span className="app-list-sub">
                    {o.restaurant_name ?? "Restaurant"}
                    {o.driver_name ? ` · Driver ${o.driver_name}` : ""}
                    {o.created_at
                      ? ` · ${new Date(o.created_at).toLocaleString()}`
                      : ""}
                  </span>
                </div>
                {o.status === "ASSIGNED" && (
                  <div className="app-actions">
                    <label className="app-field app-field-inline">
                      <span className="app-visually-hidden">
                        Choose a replacement driver
                      </span>
                      <select
                        className="app-input"
                        value={selectedDriver[o.id] ?? ""}
                        onChange={(e) =>
                          setSelectedDriver({ ...selectedDriver, [o.id]: e.target.value })
                        }
                      >
                        <option value="">Choose a driver…</option>
                        {onlineDrivers.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.full_name ?? d.name ?? d.email ?? d.id}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="app-field app-field-inline">
                      <span className="app-visually-hidden">Override reason</span>
                      <input
                        className="app-input"
                        placeholder="Reason for override"
                        value={overrideReason[o.id] ?? ""}
                        onChange={(e) =>
                          setOverrideReason({ ...overrideReason, [o.id]: e.target.value })
                        }
                      />
                    </label>
                    <button
                      type="button"
                      className="app-btn app-btn-small"
                      disabled={busyId === o.id}
                      onClick={() => runAssign(o.id, true)}
                    >
                      Override assignment
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Online drivers">
        <h2>Online drivers ({onlineDrivers.length})</h2>
        {onlineDrivers.length === 0 ? (
          <p>No drivers are online right now.</p>
        ) : (
          <ul className="app-list">
            {onlineDrivers.map((d) => (
              <li key={d.id} className="app-list-row">
                <span>
                  <strong>{d.full_name ?? d.name ?? d.email ?? d.id}</strong>
                  <span className="app-list-sub">{d.email ?? ""}</span>
                </span>
                <span className="app-badge app-badge-done">Online</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
