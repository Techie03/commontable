// Customer order history. The API scopes this list to the signed in
// customer; the page never sees anyone else's orders.

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import StatusBadge from "@/components/StatusBadge";
import { ApiError, listOrders } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCents } from "@/lib/money";
import { orderDisplayName, orderFees, type Order } from "@/lib/types";

export default function OrdersPage() {
  return (
    <AppShell>
      <OrderHistory />
    </AppShell>
  );
}

function OrderHistory() {
  const { user, ready } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listOrders();
      setOrders(list);
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("Could not load your orders.");
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

  if (offline) {
    return <ApiOffline onRetry={() => { setOffline(false); load(); }} />;
  }

  if (!ready || loading) {
    return <p>Loading your orders…</p>;
  }

  if (!user) {
    return (
      <div>
        <h1>My orders</h1>
        <p>
          <Link href="/login">Sign in</Link> to see your order history, or{" "}
          <Link href="/register">create an account</Link>.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>My orders</h1>
      <p className="app-lede">
        Past and current orders, newest first.
      </p>
      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}
      {orders.length === 0 ? (
        <p>
          No orders yet. <Link href="/order">Place your first order</Link>.
        </p>
      ) : (
        <ul className="app-list">
          {orders.map((o) => (
            <li key={o.id} className="app-list-row">
              <Link href={`/order/${o.id}`} className="app-list-link">
                <span>
                  <strong>{orderDisplayName(o)}</strong>
                  <span className="app-list-sub">
                    {o.restaurant_name ?? "Restaurant"} ·{" "}
                    {o.fulfillment_type === "pickup"
                      ? "Pickup"
                      : "Standard delivery"}
                    {o.created_at
                      ? ` · ${new Date(o.created_at).toLocaleString()}`
                      : ""}
                  </span>
                </span>
                <span className="app-list-right">
                  <StatusBadge status={o.status} />
                  <strong>{formatCents(orderFees(o).total_cents)}</strong>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
