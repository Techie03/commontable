// Customer ordering flow: address + serviceability, restaurant list,
// menu and cart, checkout (pickup or Standard only), place order.
// Slice scope only: no Saver, no Express, no batching, no loyalty.
// Payment is a labeled demo stub: no real money moves.

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import FeeBreakdown from "@/components/FeeBreakdown";
import { ApiError, checkServiceability, createPaymentIntent, getMenu, listAllComingSoonRestaurants, listOrders, listRestaurants, placeOrder } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCents } from "@/lib/money";
import {
  restaurantAddress,
  type DeliveryAddress,
  type FeeBreakdown as Fees,
  type MenuItem,
  type Order,
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

// The pilot covers Denton only, so the feed opens on Denton by default
// (Uber Eats style: restaurants first, address changeable, never a gate).
const DENTON_ADDRESS: DeliveryAddress = {
  line1: "",
  line2: "",
  city: "Denton",
  state: "TX",
  postal_code: "76201",
};

// Pilot zone bounds from the seed zone: lng -97.20 to -97.05,
// lat 33.12 to 33.30.
const DENTON_BOUNDS = { lngMin: -97.2, lngMax: -97.05, latMin: 33.12, latMax: 33.3 };

function inDentonZone(lat: number, lng: number): boolean {
  return (
    lng >= DENTON_BOUNDS.lngMin &&
    lng <= DENTON_BOUNDS.lngMax &&
    lat >= DENTON_BOUNDS.latMin &&
    lat <= DENTON_BOUNDS.latMax
  );
}

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

// Food emoji per cuisine, for the category tiles and for cards without
// a photo. Visual treatment only: no restaurant photo is invented.
const CATEGORY_EMOJI: Array<[RegExp, string]> = [
  [/pizza/i, "🍕"],
  [/burger/i, "🍔"],
  [/mexican|taco/i, "🌮"],
  [/indian/i, "🍛"],
  [/chinese/i, "🥡"],
  [/thai/i, "🍜"],
  [/barbecue|bbq/i, "🍖"],
  [/sushi|japanese/i, "🍣"],
  [/italian|pasta/i, "🍝"],
  [/breakfast|brunch/i, "🥞"],
  [/coffee|cafe/i, "☕"],
  [/bakery|donut/i, "🥐"],
  [/dessert|ice cream/i, "🍰"],
  [/fast food/i, "🍟"],
  [/grocery/i, "🛒"],
  [/vegan|vegetarian|salad/i, "🥗"],
  [/seafood|fish/i, "🦐"],
  [/chicken/i, "🍗"],
  [/sandwich|deli/i, "🥪"],
  [/korean/i, "🍚"],
  [/vietnamese|pho/i, "🍜"],
  [/mediterranean|greek/i, "🥙"],
  [/american/i, "🍔"],
];

function categoryEmoji(category?: string | null): string {
  if (!category) return "🍽️";
  for (const [re, emoji] of CATEGORY_EMOJI) {
    if (re.test(category)) return emoji;
  }
  return "🍽️";
}

function RestaurantCard({
  r,
  footer,
}: {
  r: Restaurant;
  footer?: ReactNode;
}) {
  const rating =
    r.rating_avg != null
      ? `★ ${r.rating_avg.toFixed(1)}${r.rating_count ? ` (${r.rating_count.toLocaleString()})` : ""}`
      : null;
  return (
    <article className="app-feed-card">
      {r.card_image_url ? (
        <img
          src={r.card_image_url}
          alt=""
          className="app-feed-card-img"
          loading="lazy"
        />
      ) : (
        <div className="app-feed-card-ph" aria-hidden="true">
          {categoryEmoji(r.primary_category)}
        </div>
      )}
      <div className="app-feed-card-body">
        <h3 className="app-feed-card-title">{r.name}</h3>
        <p className="app-feed-card-sub">
          {[r.primary_category, rating, restaurantAddress(r)]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {footer}
      </div>
    </article>
  );
}

// A past order as a wide photo card: the restaurant's photo when the
// feed knows it, otherwise a cuisine emoji. Shows only real facts:
// the order date and total. No invented delivery time or fee.
function PastOrderCard({
  order,
  restaurant,
  onOrderAgain,
}: {
  order: Order;
  restaurant?: Restaurant;
  onOrderAgain?: (r: Restaurant) => void;
}) {
  const rating =
    restaurant?.rating_avg != null
      ? `★ ${restaurant.rating_avg.toFixed(1)}${restaurant.rating_count ? ` (${restaurant.rating_count.toLocaleString()})` : ""}`
      : null;
  const date = order.created_at
    ? new Date(order.created_at).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      })
    : null;
  const total =
    order.total_cents != null ? formatCents(order.total_cents) : null;
  return (
    <article className="app-feed-card">
      {restaurant?.card_image_url ? (
        <img
          src={restaurant.card_image_url}
          alt=""
          className="app-feed-card-img"
          loading="lazy"
        />
      ) : (
        <div className="app-feed-card-ph" aria-hidden="true">
          {categoryEmoji(restaurant?.primary_category)}
        </div>
      )}
      <div className="app-feed-card-body">
        <h3 className="app-feed-card-title">
          {order.restaurant_name ?? restaurant?.name ?? "Restaurant"}
        </h3>
        <p className="app-feed-card-sub">
          {[rating, date ? `Ordered ${date}` : null, total]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <span className="app-feed-card-actions">
          <Link
            href={`/order/${order.id}`}
            className="app-btn app-btn-small app-btn-ghost"
          >
            View order
          </Link>
          {restaurant && onOrderAgain && (
            <button
              type="button"
              className="app-btn app-btn-small"
              onClick={() => onOrderAgain(restaurant)}
            >
              Order again
            </button>
          )}
        </span>
      </div>
    </article>
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
  // Feed-first discovery: the address lives in a pill + editor modal,
  // never as a gate in front of the restaurant list.
  const [addressOpen, setAddressOpen] = useState(false);
  const [draftAddress, setDraftAddress] = useState<DeliveryAddress>(EMPTY_ADDRESS);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationNote, setLocationNote] = useState<string | null>(null);
  const [pastOrders, setPastOrders] = useState<Order[]>([]);

  // Restore a saved draft (address, cart) after a sign in round trip,
  // then load the feed immediately for the saved or default location.
  // No form gate: Denton is the default because the pilot covers Denton.
  useEffect(() => {
    const draft = loadDraft();
    let start: DeliveryAddress = { ...DENTON_ADDRESS };
    if (draft) {
      setCart(draft.cart ?? []);
      setFulfillment(draft.fulfillment ?? "standard");
      setTipCents(draft.tipCents ?? 0);
      const postal = draft.address.postal_code?.trim();
      const city = draft.address.city?.trim();
      if (postal && city) start = draft.address;
    }
    setAddress(start);
    void resolveLocation(start);
    if (draft?.restaurantId) {
      listRestaurants(start.postal_code || undefined)
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

  // Past orders for the signed in customer, newest first. A failed load
  // just hides the section; the feed does not depend on it.
  useEffect(() => {
    if (!ready || !user) return;
    listOrders()
      .then(setPastOrders)
      .catch(() => undefined);
  }, [ready, user]);

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
      // Only active restaurants may serve. The API must not return
      // anything else here; filter defensively so a prospect or a
      // pending restaurant can never reach the customer as serving.
      setRestaurants(
        all.filter((r) => r.status !== "prospect" && r.status !== "pending")
      );
      // Coming soon: Denton restaurants not serving yet — census
      // prospects that have not joined, plus registered restaurants
      // awaiting approval. Read-only directory, never orderable. Load
      // every page so "Show all" truly shows all of them, not just the
      // first 100.
      const soon = await listAllComingSoonRestaurants(postalCode);
      setComingSoon(soon.items);
      setComingSoonTotal(soon.total);
    } catch (err) {
      handleApiError(err);
    } finally {
      setLoadingRestaurants(false);
    }
  }, [handleApiError]);

  // Resolve the delivery location and load its feed. Runs on mount for
  // the saved or default location, and whenever the address changes.
  const resolveLocation = useCallback(async (addr: DeliveryAddress) => {
    const postal = addr.postal_code.trim();
    const city = addr.city.trim();
    if (!postal || !city) return;
    setChecking(true);
    setError(null);
    try {
      const res = await checkServiceability(postal, city);
      setService(res);
      if (res.serviceable) {
        if (!res.fulfillment_options.includes("standard")) {
          setFulfillment("pickup");
        }
        await loadRestaurants(postal);
      } else {
        setRestaurants([]);
        setComingSoon([]);
        setComingSoonTotal(0);
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setChecking(false);
    }
  }, [handleApiError, loadRestaurants]);

  // Save the address from the editor modal and reload the feed for it.
  const applyAddress = useCallback((next: DeliveryAddress) => {
    if (!next.postal_code.trim() || !next.city.trim()) {
      setError("Enter a postal code and city for delivery.");
      return;
    }
    setAddressOpen(false);
    setAddress(next);
    setSelected(null);
    setMenu([]);
    setLocationNote(null);
    void resolveLocation(next);
  }, [resolveLocation]);

  // Back to the pilot zone when the current address is not serviceable.
  const browseDenton = useCallback(() => {
    const next = { ...DENTON_ADDRESS };
    setAddress(next);
    setSelected(null);
    setMenu([]);
    setLocationNote(null);
    void resolveLocation(next);
  }, [resolveLocation]);

  // Device location, from the address editor: inside the Denton zone it
  // sets the delivery area to Denton; outside it says so plainly.
  const handleUseCurrentLocation = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setLocationNote("Your device does not share its location. Enter a Denton address instead.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        if (inDentonZone(pos.coords.latitude, pos.coords.longitude)) {
          setDraftAddress({ ...DENTON_ADDRESS });
          setLocationNote("You are in Denton. Add your street address to complete the delivery address.");
        } else {
          setLocationNote("You are outside the Denton pilot zone. Delivery is only available in Denton for now.");
        }
      },
      () => {
        setLocating(false);
        setLocationNote("Could not get your location. Enter a Denton address instead.");
      },
      { timeout: 10000 }
    );
  }, []);

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

  // Feed state: what the delivery pill shows, the category chips, and
  // the search + category filtered lists.
  const deliverLabel = address.line1.trim()
    ? `${address.line1.trim()}, ${address.city.trim()} ${address.postal_code.trim()}`
    : address.postal_code.trim()
      ? `${address.city.trim()}, ${address.state.trim()} ${address.postal_code.trim()}`
      : "Set delivery address";

  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of [...restaurants, ...comingSoon]) {
      const c = r.primary_category?.trim();
      if (c) counts.set(c, (counts.get(c) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name]) => name);
  }, [restaurants, comingSoon]);

  const matchesFeed = useCallback((r: Restaurant) => {
    if (category && r.primary_category !== category) return false;
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      r.name.toLowerCase().includes(q) ||
      (r.primary_category ?? "").toLowerCase().includes(q)
    );
  }, [category, search]);

  const visibleServing = useMemo(
    () => restaurants.filter(matchesFeed),
    [restaurants, matchesFeed]
  );
  const visibleSoon = useMemo(
    () => comingSoon.filter(matchesFeed),
    [comingSoon, matchesFeed]
  );
  const filtering = search.trim() !== "" || category !== null;
  const soonShown =
    filtering || showAllComingSoon ? visibleSoon : visibleSoon.slice(0, 12);
  // Featured row: pilots with a collected menu and a photo. Only shown
  // when nothing is filtered, like the reference app's featured rail.
  const featured = useMemo(
    () => comingSoon.filter((r) => r.has_menu && r.card_image_url),
    [comingSoon]
  );

  const firstName = user?.full_name?.trim().split(" ")[0] || null;
  const cartCount = useMemo(
    () => cart.reduce((n, line) => n + line.quantity, 0),
    [cart]
  );
  // Past orders, one card per restaurant (most recent order each),
  // newest first. The demo restaurant never surfaces here.
  const pastRestaurants = useMemo(() => {
    const seen = new Set<string>();
    const out: Array<{ order: Order; restaurant?: Restaurant }> = [];
    for (const o of pastOrders) {
      if (o.status !== "COMPLETED" && o.status !== "DELIVERED") continue;
      // Demo Diner never surfaces here. The API returns restaurant_id
      // as a number, so compare as a string; the name check is backup.
      if (String(o.restaurant_id) === "1") continue;
      if (o.restaurant_name === "Demo Diner") continue;
      if (seen.has(o.restaurant_id)) continue;
      seen.add(o.restaurant_id);
      out.push({
        order: o,
        restaurant: [...restaurants, ...comingSoon].find(
          (r) => String(r.id) === String(o.restaurant_id)
        ),
      });
    }
    return out.slice(0, 6);
  }, [pastOrders, restaurants, comingSoon]);

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
      <h1>{firstName ? `Welcome back, ${firstName}` : "Order food"}</h1>
      <p className="app-lede">
        Restaurant menu prices, one clear delivery fee, and no hidden markups.
      </p>

      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      {/* Delivery or pickup: sets how the order is fulfilled at checkout. */}
      <div className="app-mode-tabs" role="tablist" aria-label="Delivery or pickup">
        <button
          type="button"
          role="tab"
          aria-selected={fulfillment !== "pickup"}
          className={`app-mode-tab${fulfillment !== "pickup" ? " active" : ""}`}
          onClick={() => setFulfillment("standard")}
        >
          🛵 Delivery
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={fulfillment === "pickup"}
          className={`app-mode-tab${fulfillment === "pickup" ? " active" : ""}`}
          onClick={() => setFulfillment("pickup")}
        >
          🛍️ Pickup
        </button>
      </div>

      {/* Top bar: delivery location + profile + cart, like the reference
          app. No bell: there is no notifications system yet. */}
      <div className="app-topbar">
        <button
          type="button"
          className="app-location-button"
          onClick={() => {
            setDraftAddress(address);
            setLocationNote(null);
            setAddressOpen(true);
          }}
        >
          <span className="app-location-value">{deliverLabel}</span>
          <span aria-hidden="true">▾</span>
        </button>
        <span className="app-topbar-actions">
          <Link
            href={user ? "/orders" : "/login"}
            className="app-icon-button"
            aria-label={user ? "My orders" : "Sign in"}
          >
            {user && firstName ? firstName.charAt(0).toUpperCase() : "👤"}
          </Link>
          <button
            type="button"
            className="app-icon-button"
            aria-label={`Cart, ${cartCount} items`}
            onClick={() =>
              document
                .getElementById("order-checkout")
                ?.scrollIntoView({ behavior: "smooth" })
            }
          >
            🛒
            {cartCount > 0 && (
              <span className="app-cart-badge">{cartCount}</span>
            )}
          </button>
        </span>
      </div>

      {locationNote && (
        <p className="app-notice" role="status">
          {locationNote}
        </p>
      )}

      {service && !service.serviceable && (
        <p className="app-notice" role="status">
          We do not deliver to {address.postal_code.trim()} yet. The pilot
          covers Denton.{" "}
          <button
            type="button"
            className="app-link-button"
            onClick={browseDenton}
          >
            Browse Denton restaurants
          </button>
        </p>
      )}

      {checking && !service ? (
        <p>Finding restaurants near you…</p>
      ) : (
        <>
          {categories.length > 0 && (
            <div className="app-category-chips" role="group" aria-label="Cuisines">
              <button
                type="button"
                className={`app-category-chip${category === null ? " active" : ""}`}
                onClick={() => setCategory(null)}
              >
                <span aria-hidden="true">🍽️</span> All
              </button>
              {categories.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`app-category-chip${category === c ? " active" : ""}`}
                  onClick={() => setCategory(category === c ? null : c)}
                >
                  <span aria-hidden="true">{categoryEmoji(c)}</span> {c}
                </button>
              ))}
            </div>
          )}

          {!filtering && featured.length > 0 && (
            <section aria-label="Featured restaurants">
              <h2>Featured</h2>
              <div className="app-featured-row">
                {featured.map((r) => (
                  <RestaurantCard
                    key={r.id}
                    r={r}
                    footer={
                      <span className="app-feed-card-actions">
                        <span className="app-tag app-tag-muted">Coming soon</span>
                        {r.has_menu && (
                          <Link
                            href={`/menu/${r.id}`}
                            className="app-btn app-btn-small app-btn-ghost"
                          >
                            View menu
                          </Link>
                        )}
                      </span>
                    }
                  />
                ))}
              </div>
            </section>
          )}

          {user && pastRestaurants.length > 0 && (
            <section aria-label="Your past orders">
              <div className="app-section-head">
                <h2>Your past orders</h2>
                <Link
                  href="/orders"
                  className="app-icon-button"
                  aria-label="See all orders"
                >
                  →
                </Link>
              </div>
              <div className="app-past-row">
                {pastRestaurants.map(({ order, restaurant }) => (
                  <PastOrderCard
                    key={order.id}
                    order={order}
                    restaurant={restaurant}
                    onOrderAgain={
                      restaurant &&
                      restaurants.some((r) => r.id === restaurant.id)
                        ? (r) => {
                            void handleSelectRestaurant(r);
                            document
                              .getElementById("order-menu")
                              ?.scrollIntoView({ behavior: "smooth" });
                          }
                        : undefined
                    }
                  />
                ))}
              </div>
            </section>
          )}

          <section aria-label="Restaurants serving now">
            <h2>Serving now</h2>
            {loadingRestaurants ? (
              <p>Loading restaurants…</p>
            ) : visibleServing.length === 0 ? (
              <p>
                No restaurants are serving this address yet. Below, you can
                browse real menus from local restaurants coming soon.
              </p>
            ) : (
              <div className="app-feed-grid">
                {visibleServing.map((r) => (
                  <RestaurantCard
                    key={r.id}
                    r={r}
                    footer={
                      <button
                        type="button"
                        className="app-btn app-btn-small"
                        onClick={() => {
                          void handleSelectRestaurant(r);
                          document
                            .getElementById("order-menu")
                            ?.scrollIntoView({ behavior: "smooth" });
                        }}
                      >
                        {selected?.id === r.id ? "Viewing menu" : "View menu"}
                      </button>
                    }
                  />
                ))}
              </div>
            )}
          </section>

          {comingSoonTotal > 0 && (
            <section aria-label="Restaurants coming soon">
              <h2>Coming soon in Denton</h2>
              <p className="app-lede">
                {comingSoonTotal} local restaurant
                {comingSoonTotal === 1 ? "" : "s"} near{" "}
                {address.postal_code.trim()} are coming soon. Ordering opens
                as each one comes on board.
              </p>
              <div className="app-feed-grid">
                {soonShown.map((r) => (
                  <RestaurantCard
                    key={r.id}
                    r={r}
                    footer={
                      <span className="app-feed-card-actions">
                        <span className="app-tag app-tag-muted">
                          {r.status === "pending"
                            ? "Recently joined"
                            : "Coming soon"}
                        </span>
                        {r.has_menu && (
                          <Link
                            href={`/menu/${r.id}`}
                            className="app-btn app-btn-small app-btn-ghost"
                          >
                            View menu
                          </Link>
                        )}
                      </span>
                    }
                  />
                ))}
              </div>
              {!filtering && comingSoonTotal > 12 && (
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
              {filtering &&
                visibleSoon.length === 0 &&
                visibleServing.length === 0 && (
                  <p>No restaurants match that search.</p>
                )}
            </section>
          )}
        </>
      )}

      {/* Address editor: a modal, not a gate. */}
      {addressOpen && (
        <div
          className="app-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Delivery address"
          onClick={(e) => {
            if (e.target === e.currentTarget) setAddressOpen(false);
          }}
        >
          <div className="app-modal-sheet">
            <h2>Delivery address</h2>
            <div className="app-form-grid">
              <label className="app-field app-field-wide">
                <span>Street address</span>
                <input
                  className="app-input"
                  value={draftAddress.line1}
                  onChange={(e) =>
                    setDraftAddress({ ...draftAddress, line1: e.target.value })
                  }
                  placeholder="123 Main St"
                  autoComplete="street-address"
                />
              </label>
              <label className="app-field">
                <span>Apt, suite, or floor (optional)</span>
                <input
                  className="app-input"
                  value={draftAddress.line2 ?? ""}
                  onChange={(e) =>
                    setDraftAddress({ ...draftAddress, line2: e.target.value })
                  }
                  placeholder="Apt 4"
                />
              </label>
              <label className="app-field">
                <span>City</span>
                <input
                  className="app-input"
                  value={draftAddress.city}
                  onChange={(e) =>
                    setDraftAddress({ ...draftAddress, city: e.target.value })
                  }
                  placeholder="Denton"
                  autoComplete="address-level2"
                />
              </label>
              <label className="app-field app-field-narrow">
                <span>State</span>
                <input
                  className="app-input"
                  value={draftAddress.state}
                  onChange={(e) =>
                    setDraftAddress({ ...draftAddress, state: e.target.value })
                  }
                  placeholder="TX"
                  maxLength={2}
                />
              </label>
              <label className="app-field app-field-narrow">
                <span>Postal code</span>
                <input
                  className="app-input"
                  value={draftAddress.postal_code}
                  onChange={(e) =>
                    setDraftAddress({
                      ...draftAddress,
                      postal_code: e.target.value,
                    })
                  }
                  placeholder="76201"
                  inputMode="numeric"
                  autoComplete="postal-code"
                />
              </label>
            </div>
            {locationNote && (
              <p className="app-notice" role="status">
                {locationNote}
              </p>
            )}
            <div className="app-modal-actions">
              <button
                type="button"
                className="app-btn app-btn-ghost"
                onClick={handleUseCurrentLocation}
                disabled={locating}
              >
                {locating ? "Locating…" : "Use my current location"}
              </button>
              <button
                type="button"
                className="app-btn app-btn-ghost"
                onClick={() => setAddressOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="app-btn"
                onClick={() => applyAddress(draftAddress)}
              >
                Save address
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating search + cart bar, like the reference app. */}
      <div className="app-bottombar">
        <label className="app-bottombar-search">
          <span className="app-visually-hidden">Search restaurants</span>
          <input
            className="app-input"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search CommonTable"
          />
        </label>
        <button
          type="button"
          className="app-bottombar-cart"
          aria-label={`Cart, ${cartCount} items`}
          onClick={() =>
            document
              .getElementById("order-checkout")
              ?.scrollIntoView({ behavior: "smooth" })
          }
        >
          🛒{cartCount > 0 ? ` ${cartCount}` : ""}
        </button>
      </div>


      {/* Menu + cart */}
      {selected && (
        <section className="app-card" aria-label="Menu" id="order-menu">
          <h2>Menu at {selected.name}</h2>
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

      {/* Checkout */}
      {selected && cart.length > 0 && (
        <section className="app-card" aria-label="Checkout" id="order-checkout">
          <h2>Checkout</h2>
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
