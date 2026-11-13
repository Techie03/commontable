// Customer ordering flow: address + serviceability, restaurant list,
// menu and cart, checkout (pickup or Standard only), place order.
// Slice scope only: no Saver, no Express, no batching, no loyalty.
// Payment is a labeled demo stub: no real money moves.

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import FeeBreakdown from "@/components/FeeBreakdown";
import { ApiError, checkServiceability, createPaymentIntent, getMenu, listComingSoonRestaurants, listRestaurants, placeOrder } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCents } from "@/lib/money";
import {
  restaurantAddress,
  type DeliveryAddress,
  type FeeBreakdown as Fees,
  type MenuItem,
  type Restaurant,
  type Serviceability,
} from "@/lib/types";

// Contract §5 pricing defaults, used ONLY for the pre-order estimate.
// The authoritative breakdown comes back from POST /orders and is shown
// on the tracking page. The estimate is labeled as an estimate.
const ESTIMATED_STANDARD_FEE_CENTS = 399;
const ESTIMATED_TAX_BPS = 825;

const DRAFT_KEY = "commontable.order_draft";

interface CartLine {
  key: string;
  menu_item_id: string;
  name: string;
  unit_price_cents: number;
  quantity: number;
  modifiers: Array<{ modifier_id: string; name: string; price_cents: number }>;
}

interface Draft {
  address: DeliveryAddress;
  restaurantId: string | null;
  cart: CartLine[];
  fulfillment: "pickup" | "standard";
  tipCents: number;
}

const EMPTY_ADDRESS: DeliveryAddress = {
  line1: "",
  line2: "",
  city: "",
  state: "TX",
  postal_code: "",
};

function loadDraft(): Draft | null {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}

function saveDraft(draft: Draft): void {
  try {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // ignore
  }
}

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `order-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function OrderPage() {
  return (
    <AppShell>
      <OrderFlow />
    </AppShell>
  );
}

function OrderFlow() {
  const { user, ready } = useAuth();
  const router = useRouter();

  const [address, setAddress] = useState<DeliveryAddress>(EMPTY_ADDRESS);
  const [service, setService] = useState<Serviceability | null>(null);
  const [checking, setChecking] = useState(false);
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [loadingRestaurants, setLoadingRestaurants] = useState(false);
  const [comingSoon, setComingSoon] = useState<Restaurant[]>([]);
  const [comingSoonTotal, setComingSoonTotal] = useState(0);
  const [showAllComingSoon, setShowAllComingSoon] = useState(false);
  const [selected, setSelected] = useState<Restaurant | null>(null);
  const [menu, setMenu] = useState<MenuItem[]>([]);
  const [loadingMenu, setLoadingMenu] = useState(false);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [fulfillment, setFulfillment] = useState<"pickup" | "standard">("standard");
  const [tipCents, setTipCents] = useState(0);
  const [customTip, setCustomTip] = useState("");
  const [placing, setPlacing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [modifierPick, setModifierPick] = useState<Record<string, Set<string>>>({});

  // Restore a saved draft (address, cart) after a sign in round trip.
  useEffect(() => {
    const draft = loadDraft();
    if (!draft) return;
    setAddress(draft.address);
    setCart(draft.cart ?? []);
    setFulfillment(draft.fulfillment ?? "standard");
    setTipCents(draft.tipCents ?? 0);
    const postal = draft.address.postal_code?.trim();
    const city = draft.address.city?.trim();
    if (postal && city) {
      checkServiceability(postal, city)
        .then((res) => {
          setService(res);
          if (res.serviceable) void loadRestaurants(postal);
        })
        .catch(() => undefined);
    }
    if (draft.restaurantId) {
      listRestaurants(postal || undefined)
        .then((all) => {
          const found = all.find((r) => String(r.id) === String(draft.restaurantId));
          if (found && found.status !== "prospect") {
            setSelected(found);
            getMenu(found.id).then(setMenu).catch(() => undefined);
          }
        })
        .catch(() => undefined);
    }
    // Only on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist the draft as the customer builds the order.
  useEffect(() => {
    saveDraft({
      address,
      restaurantId: selected?.id ?? null,
      cart,
      fulfillment,
      tipCents,
    });
  }, [address, selected, cart, fulfillment, tipCents]);

  const handleApiError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.unreachable) {
      setOffline(true);
    } else if (err instanceof ApiError) {
      setError(err.message);
    } else {
      setError("Something went wrong. Please try again.");
    }
  }, []);

  const loadRestaurants = useCallback(async (postalCode: string) => {
    setLoadingRestaurants(true);
    setError(null);
    setShowAllComingSoon(false);
    try {
      const all = await listRestaurants(postalCode);
      // Prospects are never orderable. The API must not return them here;
      // filter defensively so a prospect can never reach the customer.
      setRestaurants(all.filter((r) => r.status !== "prospect"));
      // Coming soon: real Denton restaurants that have not joined yet.
      // Read-only directory, never orderable.
      const soon = await listComingSoonRestaurants(postalCode);
      setComingSoon(soon.items);
      setComingSoonTotal(soon.total);
    } catch (err) {
      handleApiError(err);
    } finally {
      setLoadingRestaurants(false);
    }
  }, [handleApiError]);

  const handleCheckService = useCallback(async () => {
    if (!address.postal_code.trim() || !address.city.trim()) {
      setError("Enter a postal code and city to check delivery.");
      return;
    }
    setChecking(true);
    setError(null);
    setService(null);
    setSelected(null);
    setMenu([]);
    try {
      const res = await checkServiceability(address.postal_code.trim(), address.city.trim());
      setService(res);
      if (res.serviceable) {
        if (!res.fulfillment_options.includes("standard")) {
          setFulfillment("pickup");
        }
        await loadRestaurants(address.postal_code.trim());
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setChecking(false);
    }
  }, [address, handleApiError, loadRestaurants]);

  const handleSelectRestaurant = useCallback(async (r: Restaurant) => {
    setSelected(r);
    setMenu([]);
    setLoadingMenu(true);
    setError(null);
    try {
      const items = await getMenu(r.id);
      setMenu(items);
    } catch (err) {
      handleApiError(err);
    } finally {
      setLoadingMenu(false);
    }
  }, [handleApiError]);

  const toggleModifier = (itemId: string, modifierId: string) => {
    setModifierPick((prev) => {
      const next = { ...prev };
      const set = new Set(next[itemId] ?? []);
      if (set.has(modifierId)) set.delete(modifierId);
      else set.add(modifierId);
      next[itemId] = set;
      return next;
    });
  };

  const addToCart = (item: MenuItem) => {
    const pickedIds = modifierPick[item.id] ?? new Set<string>();
    const picked = (item.modifiers ?? [])
      .filter((m) => pickedIds.has(m.id))
      .map((m) => ({ modifier_id: m.id, name: m.name, price_cents: m.price_cents }));
    const unit =
      item.price_cents + picked.reduce((sum, m) => sum + m.price_cents, 0);
    const key = `${item.id}:${picked.map((m) => m.modifier_id).sort().join(",")}`;
    setCart((prev) => {
      const existing = prev.find((l) => l.key === key);
      if (existing) {
        return prev.map((l) =>
          l.key === key ? { ...l, quantity: l.quantity + 1 } : l
        );
      }
      return [
        ...prev,
        {
          key,
          menu_item_id: item.id,
          name: item.name,
          unit_price_cents: unit,
          quantity: 1,
          modifiers: picked,
        },
      ];
    });
  };

  const changeQty = (key: string, delta: number) => {
    setCart((prev) =>
      prev
        .map((l) => (l.key === key ? { ...l, quantity: l.quantity + delta } : l))
        .filter((l) => l.quantity > 0)
    );
  };

  const fees: Fees = useMemo(() => {
    const subtotal = cart.reduce(
      (sum, l) => sum + l.unit_price_cents * l.quantity,
      0
    );
    const deliveryFee =
      fulfillment === "standard" ? ESTIMATED_STANDARD_FEE_CENTS : 0;
    const tax = Math.round((subtotal * ESTIMATED_TAX_BPS) / 10000);
    return {
      subtotal_cents: subtotal,
      delivery_fee_cents: deliveryFee,
      tax_cents: tax,
      tip_cents: tipCents,
      total_cents: subtotal + deliveryFee + tax + tipCents,
      currency: "USD",
    };
  }, [cart, fulfillment, tipCents]);

  const handlePlaceOrder = async () => {
    if (!selected) return;
    if (cart.length === 0) {
      setError("Your cart is empty.");
      return;
    }
    if (fulfillment === "standard" && !address.line1.trim()) {
      setError("Enter a street address for delivery.");
      return;
    }
    if (!ready) return;
    if (!user) {
      router.push("/login");
      return;
    }
    setPlacing(true);
    setError(null);
    try {
      const order = await placeOrder(
        {
          restaurant_id: selected.id,
          items: cart.map((l) => ({
            menu_item_id: l.menu_item_id,
            quantity: l.quantity,
            modifiers: l.modifiers.map((m) => ({ modifier_id: m.modifier_id })),
          })),
          fulfillment_type: fulfillment,
          delivery_address:
            fulfillment === "standard"
              ? {
                  line1: address.line1.trim(),
                  line2: address.line2?.trim() || undefined,
                  city: address.city.trim(),
                  state: address.state.trim(),
                  postal_code: address.postal_code.trim(),
                }
              : undefined,
          tip_cents: tipCents,
          channel: "app",
        },
        newIdempotencyKey()
      );
      // Demo payment stub: records the intent, charges nothing. A failure
      // here never blocks the placed order.
      createPaymentIntent(order.id).catch(() => undefined);
      try {
        window.localStorage.removeItem(DRAFT_KEY);
      } catch {
        // ignore
      }
      router.push(`/order/${order.id}`);
    } catch (err) {
      handleApiError(err);
    } finally {
      setPlacing(false);
    }
  };

  if (offline) {
    return <ApiOffline onRetry={() => setOffline(false)} />;
  }

  const fulfillmentOptions = service?.fulfillment_options ?? ["pickup", "standard"];

  return (
    <div className="app-order">
      <h1>Order food</h1>
      <p className="app-lede">
        Restaurant menu prices, one clear delivery fee, and no hidden markups.
      </p>

      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      {/* Step 1: address + serviceability */}
      <section className="app-card" aria-label="Delivery address">
        <h2>1. Where should it go?</h2>
        <div className="app-form-grid">
          <label className="app-field app-field-wide">
            <span>Street address</span>
            <input
              className="app-input"
              value={address.line1}
              onChange={(e) => setAddress({ ...address, line1: e.target.value })}
              placeholder="123 Main St"
              autoComplete="street-address"
            />
          </label>
          <label className="app-field">
            <span>Apt, suite, or floor (optional)</span>
            <input
              className="app-input"
              value={address.line2 ?? ""}
              onChange={(e) => setAddress({ ...address, line2: e.target.value })}
              placeholder="Apt 4"
            />
          </label>
          <label className="app-field">
            <span>City</span>
            <input
              className="app-input"
              value={address.city}
              onChange={(e) => setAddress({ ...address, city: e.target.value })}
              placeholder="Denton"
              autoComplete="address-level2"
            />
          </label>
          <label className="app-field app-field-narrow">
            <span>State</span>
            <input
              className="app-input"
              value={address.state}
              onChange={(e) => setAddress({ ...address, state: e.target.value })}
              placeholder="TX"
              maxLength={2}
            />
          </label>
          <label className="app-field app-field-narrow">
            <span>Postal code</span>
            <input
              className="app-input"
              value={address.postal_code}
              onChange={(e) => setAddress({ ...address, postal_code: e.target.value })}
              placeholder="76201"
              inputMode="numeric"
              autoComplete="postal-code"
            />
          </label>
        </div>
        <button
          type="button"
          className="app-btn"
          onClick={handleCheckService}
          disabled={checking}
        >
          {checking ? "Checking…" : "Check delivery"}
        </button>
        {service && !service.serviceable && (
          <p className="app-notice" role="status">
            We do not deliver to that postal code yet. The pilot covers Denton.
            You can still pick up from a restaurant in the zone.
          </p>
        )}
        {service?.serviceable && (
          <p className="app-notice app-notice-good" role="status">
            Good news, {service.zone_name ?? "your zone"} is covered.
          </p>
        )}
      </section>

      {/* Step 2: restaurants */}
      {service?.serviceable && (
        <section className="app-card" aria-label="Restaurants">
          <h2>2. Choose a restaurant</h2>
          {loadingRestaurants ? (
            <p>Loading restaurants…</p>
          ) : restaurants.length === 0 ? (
            <p>
              No restaurants are serving this address yet. Below, you can
              browse real menus from local restaurants coming soon.
            </p>
          ) : (
            <ul className="app-list">
              {restaurants.map((r) => (
                <li key={r.id} className="app-list-row">
                  <button
                    type="button"
                    className={`app-list-button${selected?.id === r.id ? " selected" : ""}`}
                    onClick={() => handleSelectRestaurant(r)}
                  >
                    <span className="app-list-title">
                      {r.name}
                      {r.status === "demo" && (
                        <span className="app-tag">Demo restaurant</span>
                      )}
                    </span>
                    <span className="app-list-sub">
                      {[r.primary_category, restaurantAddress(r)]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Coming soon: real Denton restaurants, not yet partners */}
      {service?.serviceable && comingSoonTotal > 0 && (
        <section className="app-card" aria-label="Restaurants coming soon">
          <h2>Coming soon in Denton</h2>
          <p className="app-lede">
            {comingSoonTotal} local restaurant{comingSoonTotal === 1 ? "" : "s"}{" "}
            near {address.postal_code.trim()} {comingSoonTotal === 1 ? "has" : "have"}{" "}
            not joined CommonTable yet. Ordering opens as each one comes on
            board.
          </p>
          <ul className="app-list">
            {(showAllComingSoon ? comingSoon : comingSoon.slice(0, 12)).map((r) => (
              <li key={r.id} className="app-list-row">
                <span>
                  <span className="app-list-title">
                    {r.name}
                    <span className="app-tag app-tag-muted">Coming soon</span>
                  </span>
                  <span className="app-list-sub">
                    {[r.primary_category, restaurantAddress(r), r.phone]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </span>
                {r.has_menu && (
                  <Link
                    href={`/menu/${r.id}`}
                    className="app-btn app-btn-small app-btn-ghost"
                  >
                    View menu
                  </Link>
                )}
              </li>
            ))}
          </ul>
          {comingSoonTotal > 12 && (
            <button
              type="button"
              className="app-btn app-btn-small app-btn-ghost"
              onClick={() => setShowAllComingSoon((v) => !v)}
            >
              {showAllComingSoon
                ? "Show fewer"
                : `Show all ${comingSoonTotal} coming soon`}
            </button>
          )}
        </section>
      )}

      {/* Step 3: menu + cart */}
      {selected && (
        <section className="app-card" aria-label="Menu">
          <h2>3. Menu at {selected.name}</h2>
          {loadingMenu ? (
            <p>Loading the menu…</p>
          ) : menu.length === 0 ? (
            <p>This restaurant has no menu items listed yet.</p>
          ) : (
            <ul className="app-list">
              {menu.map((item) => (
                <li key={item.id} className="app-list-row app-menu-row">
                  {item.image_url && (
                    <img
                      src={item.image_url}
                      alt=""
                      className="app-menu-image"
                      loading="lazy"
                    />
                  )}
                  <div className="app-menu-info">
                    <span className="app-list-title">{item.name}</span>
                    {item.description && (
                      <span className="app-list-sub">{item.description}</span>
                    )}
                    <span className="app-menu-price">
                      {formatCents(item.price_cents)}
                    </span>
                    {!item.available && (
                      <span className="app-tag app-tag-muted">Unavailable</span>
                    )}
                    {(item.modifiers ?? []).length > 0 && item.available && (
                      <span className="app-modifiers">
                        {item.modifiers!.map((m) => (
                          <label key={m.id} className="app-check">
                            <input
                              type="checkbox"
                              checked={(modifierPick[item.id] ?? new Set()).has(m.id)}
                              onChange={() => toggleModifier(item.id, m.id)}
                            />
                            {m.name} (+{formatCents(m.price_cents)})
                          </label>
                        ))}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    className="app-btn app-btn-small"
                    disabled={!item.available}
                    onClick={() => addToCart(item)}
                  >
                    Add
                  </button>
                </li>
              ))}
            </ul>
          )}

          {cart.length > 0 && (
            <div className="app-cart">
              <h3>Your cart</h3>
              <ul className="app-list">
                {cart.map((line) => (
                  <li key={line.key} className="app-list-row app-cart-row">
                    <span>
                      <strong>{line.name}</strong>
                      {line.modifiers.length > 0 && (
                        <span className="app-list-sub">
                          {line.modifiers.map((m) => m.name).join(", ")}
                        </span>
                      )}
                    </span>
                    <span className="app-stepper">
                      <button
                        type="button"
                        className="app-stepper-btn"
                        aria-label="Decrease quantity"
                        onClick={() => changeQty(line.key, -1)}
                      >
                        −
                      </button>
                      <span>{line.quantity}</span>
                      <button
                        type="button"
                        className="app-stepper-btn"
                        aria-label="Increase quantity"
                        onClick={() => changeQty(line.key, 1)}
                      >
                        +
                      </button>
                    </span>
                    <span className="app-cart-line-total">
                      {formatCents(line.unit_price_cents * line.quantity)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* Step 4: checkout */}
      {selected && cart.length > 0 && (
        <section className="app-card" aria-label="Checkout">
          <h2>4. Checkout</h2>
          <fieldset className="app-fieldset">
            <legend>How do you want to get it?</legend>
            <label className="app-radio">
              <input
                type="radio"
                name="fulfillment"
                value="standard"
                checked={fulfillment === "standard"}
                disabled={!fulfillmentOptions.includes("standard")}
                onChange={() => setFulfillment("standard")}
              />
              Standard delivery
            </label>
            <label className="app-radio">
              <input
                type="radio"
                name="fulfillment"
                value="pickup"
                checked={fulfillment === "pickup"}
                disabled={!fulfillmentOptions.includes("pickup")}
                onChange={() => setFulfillment("pickup")}
              />
              Pickup (no delivery fee)
            </label>
          </fieldset>

          <div className="app-tip-row" role="group" aria-label="Tip">
            <span className="app-tip-label">Tip</span>
            {[0, 200, 300, 500].map((cents) => (
              <button
                key={cents}
                type="button"
                className={`app-tip${tipCents === cents ? " active" : ""}`}
                onClick={() => {
                  setTipCents(cents);
                  setCustomTip("");
                }}
              >
                {cents === 0 ? "No tip" : formatCents(cents)}
              </button>
            ))}
            <label className="app-field app-field-inline">
              <span className="app-visually-hidden">Custom tip in dollars</span>
              <input
                className="app-input"
                inputMode="decimal"
                placeholder="Other $"
                value={customTip}
                onChange={(e) => {
                  setCustomTip(e.target.value);
                  const n = Number.parseFloat(e.target.value);
                  setTipCents(
                    Number.isNaN(n) || n < 0 ? 0 : Math.round(n * 100)
                  );
                }}
              />
            </label>
          </div>

          <FeeBreakdown fees={fees} estimate />

          <p className="app-stub-note">
            Demo checkout: no card is charged and no real money moves. Payment
            processing is a labeled stub until a real provider is connected.
          </p>

          {!user && ready && (
            <p className="app-notice">
              You need an account to place an order. Your cart is saved, so
              sign in and come back here.{" "}
              <Link href="/login">Sign in</Link> or{" "}
              <Link href="/register">create an account</Link>.
            </p>
          )}

          <button
            type="button"
            className="app-btn app-btn-wide app-btn-large"
            onClick={handlePlaceOrder}
            disabled={placing || !ready}
          >
            {placing ? "Placing your order…" : `Place order · ${formatCents(fees.total_cents)}`}
          </button>
        </section>
      )}
    </div>
  );
}
