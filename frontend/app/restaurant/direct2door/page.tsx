// Direct2Door order intake: restaurant staff record an order that came
// through the restaurant's own website or phone line. It is created with
// channel "direct2door" at PLACED and flows through the normal queue.

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import FeeBreakdown from "@/components/FeeBreakdown";
import {
  ApiError,
  getMenu,
  getRestaurant,
  placeOrder,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCents } from "@/lib/money";
import type { MenuItem, Order, Restaurant } from "@/lib/types";

const MANUAL_ID_KEY = "commontable.restaurant_manual_id";
const ESTIMATED_STANDARD_FEE_CENTS = 399;
const ESTIMATED_TAX_BPS = 825;

export default function Direct2DoorPage() {
  return (
    <AppShell>
      <Direct2DoorForm />
    </AppShell>
  );
}

function Direct2DoorForm() {
  const { user, ready, restaurantId } = useAuth();
  const [manualId, setManualId] = useState("");
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null);
  const [menu, setMenu] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [qty, setQty] = useState<Record<string, number>>({});
  const [fulfillment, setFulfillment] = useState<"pickup" | "standard">("standard");
  const [line1, setLine1] = useState("");
  const [city, setCity] = useState("");
  const [stateCode, setStateCode] = useState("TX");
  const [postalCode, setPostalCode] = useState("");
  const [tip, setTip] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [placed, setPlaced] = useState<Order | null>(null);

  const activeId = restaurantId ?? manualId;

  useEffect(() => {
    try {
      const saved = window.sessionStorage.getItem(MANUAL_ID_KEY);
      if (saved) setManualId(saved);
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
      const [r, items] = await Promise.all([
        getRestaurant(activeId),
        getMenu(activeId),
      ]);
      setRestaurant(r);
      setMenu(items);
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("Could not load the menu.");
    } finally {
      setLoading(false);
    }
  }, [activeId]);

  useEffect(() => {
    if (!ready) return;
    load();
  }, [ready, load]);

  const lines = menu
    .map((item) => ({ item, quantity: qty[item.id] ?? 0 }))
    .filter((l) => l.quantity > 0);
  const subtotal = lines.reduce(
    (sum, l) => sum + l.item.price_cents * l.quantity,
    0
  );
  const tipCents = (() => {
    const n = Number.parseFloat(tip);
    return Number.isNaN(n) || n < 0 ? 0 : Math.round(n * 100);
  })();
  const deliveryFee = fulfillment === "standard" ? ESTIMATED_STANDARD_FEE_CENTS : 0;
  const tax = Math.round((subtotal * ESTIMATED_TAX_BPS) / 10000);

  const handleSubmit = async () => {
    if (!customerName.trim()) {
      setError("Enter the customer's name.");
      return;
    }
    if (lines.length === 0) {
      setError("Add at least one item to the order.");
      return;
    }
    if (fulfillment === "standard" && (!line1.trim() || !city.trim() || !postalCode.trim())) {
      setError("Enter the full delivery address.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const key =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `d2d-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const order = await placeOrder(
        {
          restaurant_id: activeId,
          items: lines.map((l) => ({
            menu_item_id: l.item.id,
            quantity: l.quantity,
          })),
          fulfillment_type: fulfillment,
          delivery_address:
            fulfillment === "standard"
              ? {
                  line1: line1.trim(),
                  city: city.trim(),
                  state: stateCode.trim(),
                  postal_code: postalCode.trim(),
                }
              : undefined,
          tip_cents: tipCents,
          channel: "direct2door",
          customer_name: customerName.trim(),
          customer_phone: customerPhone.trim() || undefined,
        },
        key
      );
      setPlaced(order);
      setQty({});
      setCustomerName("");
      setCustomerPhone("");
      setLine1("");
      setCity("");
      setPostalCode("");
      setTip("");
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("Could not record the order.");
    } finally {
      setSubmitting(false);
    }
  };

  if (offline) {
    return <ApiOffline onRetry={() => { setOffline(false); setLoading(true); load(); }} />;
  }

  if (!ready || loading) {
    return <p>Loading…</p>;
  }

  if (!user) {
    return (
      <div>
        <h1>Record a Direct2Door order</h1>
        <p>
          <Link href="/login">Sign in</Link> with a restaurant account to
          record Direct2Door orders.
        </p>
      </div>
    );
  }

  if (!activeId) {
    return (
      <div>
        <h1>Record a Direct2Door order</h1>
        <p>
          No restaurant is linked to your account yet. Open the{" "}
          <Link href="/restaurant">restaurant dashboard</Link> first.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>Record a Direct2Door order</h1>
      <p className="app-lede">
        For orders that come through {restaurant?.name ?? "the restaurant"}&apos;s
        own website or phone line. The order enters the normal queue as
        Direct2Door.
      </p>

      {placed && (
        <p className="app-notice app-notice-good" role="status">
          Order {placed.id.slice(0, 8)} recorded and placed. It is now in the{" "}
          <Link href="/restaurant">order queue</Link>.
        </p>
      )}
      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      <section className="app-card" aria-label="Customer details">
        <h2>Customer</h2>
        <div className="app-form-grid">
          <label className="app-field">
            <span>Customer name</span>
            <input
              className="app-input"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="Customer name"
            />
          </label>
          <label className="app-field">
            <span>Customer phone (optional)</span>
            <input
              className="app-input"
              type="tel"
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              placeholder="(555) 123-4567"
            />
          </label>
        </div>
      </section>

      <section className="app-card" aria-label="Items">
        <h2>Items</h2>
        {menu.length === 0 ? (
          <p>No menu items yet.</p>
        ) : (
          <ul className="app-list">
            {menu.map((item) => (
              <li key={item.id} className="app-list-row app-menu-row">
                <div className="app-menu-info">
                  <span className="app-list-title">{item.name}</span>
                  <span className="app-menu-price">
                    {formatCents(item.price_cents)}
                  </span>
                  {!item.available && (
                    <span className="app-tag app-tag-muted">Unavailable</span>
                  )}
                </div>
                <span className="app-stepper">
                  <button
                    type="button"
                    className="app-stepper-btn"
                    aria-label={`Remove one ${item.name}`}
                    disabled={!item.available || (qty[item.id] ?? 0) === 0}
                    onClick={() =>
                      setQty({ ...qty, [item.id]: Math.max(0, (qty[item.id] ?? 0) - 1) })
                    }
                  >
                    −
                  </button>
                  <span>{qty[item.id] ?? 0}</span>
                  <button
                    type="button"
                    className="app-stepper-btn"
                    aria-label={`Add one ${item.name}`}
                    disabled={!item.available}
                    onClick={() =>
                      setQty({ ...qty, [item.id]: (qty[item.id] ?? 0) + 1 })
                    }
                  >
                    +
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="app-card" aria-label="Fulfillment and total">
        <h2>Fulfillment and total</h2>
        <fieldset className="app-fieldset">
          <legend>How does the customer get it?</legend>
          <label className="app-radio">
            <input
              type="radio"
              name="d2d-fulfillment"
              checked={fulfillment === "standard"}
              onChange={() => setFulfillment("standard")}
            />
            Standard delivery
          </label>
          <label className="app-radio">
            <input
              type="radio"
              name="d2d-fulfillment"
              checked={fulfillment === "pickup"}
              onChange={() => setFulfillment("pickup")}
            />
            Pickup (no delivery fee)
          </label>
        </fieldset>

        {fulfillment === "standard" && (
          <div className="app-form-grid">
            <label className="app-field app-field-wide">
              <span>Street address</span>
              <input
                className="app-input"
                value={line1}
                onChange={(e) => setLine1(e.target.value)}
                placeholder="123 Main St"
              />
            </label>
            <label className="app-field">
              <span>City</span>
              <input
                className="app-input"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Denton"
              />
            </label>
            <label className="app-field app-field-narrow">
              <span>State</span>
              <input
                className="app-input"
                value={stateCode}
                onChange={(e) => setStateCode(e.target.value)}
                maxLength={2}
              />
            </label>
            <label className="app-field app-field-narrow">
              <span>Postal code</span>
              <input
                className="app-input"
                value={postalCode}
                onChange={(e) => setPostalCode(e.target.value)}
                placeholder="76201"
              />
            </label>
          </div>
        )}

        <label className="app-field app-field-narrow">
          <span>Tip ($, optional)</span>
          <input
            className="app-input"
            inputMode="decimal"
            value={tip}
            onChange={(e) => setTip(e.target.value)}
            placeholder="0.00"
          />
        </label>

        <FeeBreakdown
          fees={{
            subtotal_cents: subtotal,
            delivery_fee_cents: deliveryFee,
            tax_cents: tax,
            tip_cents: tipCents,
            total_cents: subtotal + deliveryFee + tax + tipCents,
            currency: "USD",
          }}
          estimate
        />

        <button
          type="button"
          className="app-btn app-btn-wide"
          onClick={handleSubmit}
          disabled={submitting || lines.length === 0}
        >
          {submitting ? "Recording…" : "Record order"}
        </button>
      </section>
    </div>
  );
}
