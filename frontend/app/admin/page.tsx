// Admin console: metrics, orders, users, restaurants (including prospects,
// clearly labeled unclaimed and not partners), drivers, zones, pricing,
// refunds, ledger, settlements, and support tickets.

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import StatusBadge from "@/components/StatusBadge";
import {
  adminApproveDriver,
  adminApproveRestaurant,
  adminCreatePricing,
  adminCreateZone,
  adminGetMetrics,
  adminListLedger,
  adminListPricing,
  adminListRestaurants,
  adminListSettlements,
  adminListSupport,
  adminListUsers,
  adminListZones,
  adminResolveSupport,
  adminUpdatePricing,
  adminUpdateUserRoles,
  adminUpdateZone,
  ApiError,
  createRefund,
  listOrders,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dollarsToCents, formatCents } from "@/lib/money";
import {
  normalizeRoles,
  orderDisplayName,
  orderFees,
  restaurantAddress,
  type AdminMetrics,
  type LedgerEntry,
  type Order,
  type PricingRule,
  type Restaurant,
  type RestaurantStatus,
  type Role,
  type Settlement,
  type SupportTicket,
  type User,
  type Zone,
} from "@/lib/types";

type TabId =
  | "metrics"
  | "orders"
  | "users"
  | "restaurants"
  | "drivers"
  | "zones"
  | "pricing"
  | "refunds"
  | "ledger"
  | "settlements"
  | "support";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "metrics", label: "Metrics" },
  { id: "orders", label: "Orders" },
  { id: "users", label: "Users" },
  { id: "restaurants", label: "Restaurants" },
  { id: "drivers", label: "Drivers" },
  { id: "zones", label: "Zones" },
  { id: "pricing", label: "Pricing" },
  { id: "refunds", label: "Refunds" },
  { id: "ledger", label: "Ledger" },
  { id: "settlements", label: "Settlements" },
  { id: "support", label: "Support" },
];

const ALL_ROLES: Role[] = [
  "customer",
  "restaurant_owner",
  "restaurant_manager",
  "restaurant_staff",
  "driver",
  "dispatcher",
  "admin",
];

const RESTAURANT_STATUSES: Array<RestaurantStatus | ""> = [
  "",
  "prospect",
  "pending",
  "active",
  "suspended",
  "demo",
];

export default function AdminPage() {
  return (
    <AppShell>
      <AdminConsole />
    </AppShell>
  );
}

function AdminConsole() {
  const { user, ready, hasRole } = useAuth();
  const [tab, setTab] = useState<TabId>("metrics");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [restaurantFilter, setRestaurantFilter] = useState<RestaurantStatus | "">("");
  const [zones, setZones] = useState<Zone[]>([]);
  const [pricing, setPricing] = useState<PricingRule[]>([]);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [tickets, setTickets] = useState<SupportTicket[]>([]);

  // Role editor state
  const [roleUserId, setRoleUserId] = useState("");
  const [roleToAdd, setRoleToAdd] = useState<Role>("customer");
  const [roleToRemove, setRoleToRemove] = useState<Role>("customer");
  const [roleScope, setRoleScope] = useState("");

  // Zone form state
  const [zoneName, setZoneName] = useState("");
  const [zonePostal, setZonePostal] = useState("");
  const [zoneTax, setZoneTax] = useState("8.25");

  // Pricing form state
  const [pricingZoneId, setPricingZoneId] = useState("");
  const [pricingFee, setPricingFee] = useState("3.99");
  const [pricingDriverPay, setPricingDriverPay] = useState("2.50");
  const [pricingFulfillment, setPricingFulfillment] = useState("0.75");
  const [editingPricing, setEditingPricing] = useState<PricingRule | null>(null);
  const [editFee, setEditFee] = useState("");

  // Refund form state
  const [refundOrderId, setRefundOrderId] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundReason, setRefundReason] = useState("");
  const [refundDone, setRefundDone] = useState(false);

  const handleError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.unreachable) setOffline(true);
    else if (err instanceof ApiError) setError(err.message);
    else setError("Something went wrong. Please try again.");
  }, []);

  const loadTab = useCallback(
    async (t: TabId, statusFilter?: RestaurantStatus | "") => {
      setLoading(true);
      setError(null);
      try {
        if (t === "metrics") setMetrics(await adminGetMetrics());
        if (t === "orders") setOrders(await listOrders());
        if (t === "users" || t === "drivers") setUsers(await adminListUsers());
        if (t === "restaurants") {
          setRestaurants(
            await adminListRestaurants(statusFilter || undefined)
          );
        }
        if (t === "zones") setZones(await adminListZones());
        if (t === "pricing") {
          const [rules, z] = await Promise.all([
            adminListPricing(),
            adminListZones().catch(() => [] as Zone[]),
          ]);
          setPricing(rules);
          setZones(z);
        }
        if (t === "ledger") setLedger(await adminListLedger());
        if (t === "settlements") setSettlements(await adminListSettlements());
        if (t === "support") setTickets(await adminListSupport());
      } catch (err) {
        handleError(err);
      } finally {
        setLoading(false);
      }
    },
    [handleError]
  );

  useEffect(() => {
    if (!ready) return;
    if (!user || !hasRole("admin")) {
      setLoading(false);
      return;
    }
    loadTab(tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, user, tab]);

  const switchTab = (t: TabId) => {
    setTab(t);
    setRefundDone(false);
  };

  const changeRestaurantFilter = (status: RestaurantStatus | "") => {
    setRestaurantFilter(status);
    loadTab("restaurants", status);
  };

  if (offline) {
    return <ApiOffline onRetry={() => { setOffline(false); loadTab(tab, restaurantFilter); }} />;
  }

  if (!ready || loading) {
    return <p>Loading the admin console…</p>;
  }

  if (!user) {
    return (
      <div>
        <h1>Admin</h1>
        <p>
          <Link href="/login">Sign in</Link> with an admin account to open
          the console.
        </p>
      </div>
    );
  }

  if (!hasRole("admin")) {
    return (
      <div>
        <h1>Admin</h1>
        <p>Your account does not have admin access.</p>
      </div>
    );
  }

  const prospectCount = restaurants.filter((r) => r.status === "prospect").length;
  const driverUsers = users.filter((u) =>
    normalizeRoles(u).some((r) => r.role === "driver")
  );

  return (
    <div>
      <h1>Admin console</h1>
      <nav className="app-tabs" aria-label="Admin sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`app-tab${tab === t.id ? " active" : ""}`}
            onClick={() => switchTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      {tab === "metrics" && (
        <section aria-label="Metrics">
          <h2>Metrics</h2>
          {metrics == null ? (
            <p>No metrics available yet.</p>
          ) : (
            <>
              <div className="app-stat-strip">
                <div className="app-stat">
                  <span className="app-stat-number">{metrics.orders_today ?? 0}</span>
                  <span className="app-stat-label">Orders today</span>
                </div>
                <div className="app-stat">
                  <span className="app-stat-number">
                    {formatCents(metrics.fees_cents_today ?? metrics.revenue_cents_today)}
                  </span>
                  <span className="app-stat-label">Fees today</span>
                </div>
                <div className="app-stat">
                  <span className="app-stat-number">
                    {metrics.avg_prep_minutes != null
                      ? `${metrics.avg_prep_minutes} min`
                      : "—"}
                  </span>
                  <span className="app-stat-label">Average prep time</span>
                </div>
                <div className="app-stat">
                  <span className="app-stat-number">
                    {metrics.on_time_rate != null
                      ? `${Math.round(metrics.on_time_rate * 100)}%`
                      : "—"}
                  </span>
                  <span className="app-stat-label">On time</span>
                </div>
              </div>
              {metrics.orders_by_status && (
                <>
                  <h3>Orders by status</h3>
                  <ul className="app-list">
                    {Object.entries(metrics.orders_by_status).map(([status, count]) => (
                      <li key={status} className="app-list-row">
                        <StatusBadge status={status} />
                        <strong>{count}</strong>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </section>
      )}

      {tab === "orders" && (
        <section aria-label="Orders">
          <h2>Orders ({orders.length})</h2>
          {orders.length === 0 ? (
            <p>No orders yet.</p>
          ) : (
            <div className="app-table-wrap">
              <table className="app-table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Restaurant</th>
                    <th>Fulfillment</th>
                    <th>Status</th>
                    <th>Total</th>
                    <th>Placed</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.id}>
                      <td>
                        <Link href={`/order/${o.id}`}>{orderDisplayName(o)}</Link>
                      </td>
                      <td>{o.restaurant_name ?? o.restaurant_id.slice(0, 8)}</td>
                      <td>{o.fulfillment_type === "pickup" ? "Pickup" : "Standard"}</td>
                      <td><StatusBadge status={o.status} /></td>
                      <td>{formatCents(orderFees(o).total_cents)}</td>
                      <td>
                        {o.created_at
                          ? new Date(o.created_at).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "users" && (
        <section aria-label="Users">
          <h2>Users ({users.length})</h2>
          <div className="app-card">
            <h3>Change a user&apos;s roles</h3>
            <div className="app-form-grid">
              <label className="app-field app-field-wide">
                <span>User</span>
                <select
                  className="app-input"
                  value={roleUserId}
                  onChange={(e) => setRoleUserId(e.target.value)}
                >
                  <option value="">Choose a user…</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name ? `${u.full_name} (${u.email})` : u.email}
                    </option>
                  ))}
                </select>
              </label>
              <label className="app-field">
                <span>Add role</span>
                <select
                  className="app-input"
                  value={roleToAdd}
                  onChange={(e) => setRoleToAdd(e.target.value as Role)}
                >
                  {ALL_ROLES.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </label>
              <label className="app-field">
                <span>Restaurant scope (for restaurant roles)</span>
                <input
                  className="app-input"
                  value={roleScope}
                  onChange={(e) => setRoleScope(e.target.value)}
                  placeholder="Restaurant id"
                />
              </label>
            </div>
            <div className="app-actions">
              <button
                type="button"
                className="app-btn app-btn-small"
                disabled={!roleUserId || busy === "roles"}
                onClick={async () => {
                  setBusy("roles");
                  setError(null);
                  try {
                    await adminUpdateUserRoles(roleUserId, {
                      add: [roleToAdd],
                      scope_restaurant_id: roleScope.trim() || undefined,
                    });
                    await loadTab("users");
                  } catch (err) {
                    handleError(err);
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                Add role
              </button>
              <label className="app-field app-field-inline">
                <span className="app-visually-hidden">Remove role</span>
                <select
                  className="app-input"
                  value={roleToRemove}
                  onChange={(e) => setRoleToRemove(e.target.value as Role)}
                >
                  {ALL_ROLES.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="app-btn app-btn-small app-btn-danger"
                disabled={!roleUserId || busy === "roles"}
                onClick={async () => {
                  setBusy("roles");
                  setError(null);
                  try {
                    await adminUpdateUserRoles(roleUserId, {
                      remove: [roleToRemove],
                    });
                    await loadTab("users");
                  } catch (err) {
                    handleError(err);
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                Remove role
              </button>
            </div>
          </div>
          {users.length === 0 ? (
            <p>No users yet.</p>
          ) : (
            <ul className="app-list">
              {users.map((u) => (
                <li key={u.id} className="app-list-row">
                  <span>
                    <strong>{u.full_name ?? u.email}</strong>
                    <span className="app-list-sub">{u.email}</span>
                  </span>
                  <span className="app-roles">
                    {normalizeRoles(u).map((r, idx) => (
                      <span key={`${r.role}-${idx}`} className="app-tag">
                        {r.role}
                        {r.scope_id ? ` · ${r.scope_id.slice(0, 8)}` : ""}
                      </span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "restaurants" && (
        <section aria-label="Restaurants">
          <h2>Restaurants ({restaurants.length})</h2>
          <p className="app-lede">
            This list includes every restaurant in the system. Prospect
            restaurants came from the Denton census: they are unclaimed and
            are not partners, and they never appear to customers.
          </p>
          <label className="app-field app-field-narrow">
            <span>Filter by status</span>
            <select
              className="app-input"
              value={restaurantFilter}
              onChange={(e) =>
                changeRestaurantFilter(e.target.value as RestaurantStatus | "")
              }
            >
              {RESTAURANT_STATUSES.map((s) => (
                <option key={s || "all"} value={s}>
                  {s === "" ? "All statuses" : s}
                </option>
              ))}
            </select>
          </label>
          {prospectCount > 0 && (
            <p className="app-notice">
              {prospectCount} prospect{prospectCount === 1 ? "" : "s"} in this
              view: unclaimed, not a partner.
            </p>
          )}
          {restaurants.length === 0 ? (
            <p>No restaurants match this filter.</p>
          ) : (
            <ul className="app-list">
              {restaurants.map((r) => (
                <li key={r.id} className="app-list-row">
                  <span>
                    <strong>{r.name}</strong>
                    <span className="app-list-sub">
                      {restaurantAddress(r)}
                      {r.primary_category ? ` · ${r.primary_category}` : ""}
                    </span>
                    <span className="app-list-sub">
                      Status: {r.status}
                      {r.status === "prospect" && (
                        <span className="app-tag app-tag-warning">
                          Prospect, unclaimed, not a partner
                        </span>
                      )}
                      {r.status === "demo" && (
                        <span className="app-tag">Demo restaurant</span>
                      )}
                    </span>
                  </span>
                  {r.status === "pending" && (
                    <button
                      type="button"
                      className="app-btn app-btn-small"
                      disabled={busy === r.id}
                      onClick={async () => {
                        setBusy(r.id);
                        setError(null);
                        try {
                          await adminApproveRestaurant(r.id);
                          await loadTab("restaurants", restaurantFilter);
                        } catch (err) {
                          handleError(err);
                        } finally {
                          setBusy(null);
                        }
                      }}
                    >
                      Approve
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "drivers" && (
        <section aria-label="Drivers">
          <h2>Drivers ({driverUsers.length})</h2>
          {driverUsers.length === 0 ? (
            <p>No driver accounts yet.</p>
          ) : (
            <ul className="app-list">
              {driverUsers.map((u) => (
                <li key={u.id} className="app-list-row">
                  <span>
                    <strong>{u.full_name ?? u.email}</strong>
                    <span className="app-list-sub">{u.email}</span>
                  </span>
                  <button
                    type="button"
                    className="app-btn app-btn-small"
                    disabled={busy === u.id}
                    onClick={async () => {
                      setBusy(u.id);
                      setError(null);
                      try {
                        await adminApproveDriver(u.id);
                        await loadTab("drivers");
                      } catch (err) {
                        handleError(err);
                      } finally {
                        setBusy(null);
                      }
                    }}
                  >
                    Approve onboarding
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "zones" && (
        <section aria-label="Zones">
          <h2>Service zones</h2>
          <div className="app-card">
            <h3>Add a zone</h3>
            <div className="app-form-grid">
              <label className="app-field">
                <span>Name</span>
                <input
                  className="app-input"
                  value={zoneName}
                  onChange={(e) => setZoneName(e.target.value)}
                  placeholder="Denton"
                />
              </label>
              <label className="app-field">
                <span>Postal codes (comma separated)</span>
                <input
                  className="app-input"
                  value={zonePostal}
                  onChange={(e) => setZonePostal(e.target.value)}
                  placeholder="76201, 76203, 76205"
                />
              </label>
              <label className="app-field app-field-narrow">
                <span>Tax rate (%)</span>
                <input
                  className="app-input"
                  inputMode="decimal"
                  value={zoneTax}
                  onChange={(e) => setZoneTax(e.target.value)}
                />
              </label>
            </div>
            <button
              type="button"
              className="app-btn"
              disabled={busy === "zone"}
              onClick={async () => {
                const tax = Number.parseFloat(zoneTax);
                if (!zoneName.trim() || Number.isNaN(tax)) {
                  setError("Enter a zone name and a valid tax rate.");
                  return;
                }
                setBusy("zone");
                setError(null);
                try {
                  await adminCreateZone({
                    name: zoneName.trim(),
                    postal_codes: zonePostal
                      .split(",")
                      .map((p) => p.trim())
                      .filter(Boolean),
                    tax_rate_bps: Math.round(tax * 100),
                    active: true,
                  });
                  setZoneName("");
                  setZonePostal("");
                  await loadTab("zones");
                } catch (err) {
                  handleError(err);
                } finally {
                  setBusy(null);
                }
              }}
            >
              Add zone
            </button>
          </div>
          {zones.length === 0 ? (
            <p>No zones yet.</p>
          ) : (
            <ul className="app-list">
              {zones.map((z) => (
                <li key={z.id} className="app-list-row">
                  <span>
                    <strong>{z.name}</strong>
                    <span className="app-list-sub">
                      Postal codes: {(z.postal_codes ?? []).join(", ") || "none"}
                      {z.tax_rate_bps != null
                        ? ` · Tax ${(z.tax_rate_bps / 100).toFixed(2)}%`
                        : ""}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="app-btn app-btn-small app-btn-ghost"
                    disabled={busy === z.id}
                    onClick={async () => {
                      setBusy(z.id);
                      setError(null);
                      try {
                        await adminUpdateZone(z.id, { active: !z.active });
                        await loadTab("zones");
                      } catch (err) {
                        handleError(err);
                      } finally {
                        setBusy(null);
                      }
                    }}
                  >
                    {z.active ? "Deactivate" : "Activate"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "pricing" && (
        <section aria-label="Pricing rules">
          <h2>Pricing rules</h2>
          <p className="app-lede">
            Delivery fees, driver pay, and fulfillment fees by zone. These
            values drive checkout totals and driver offers.
          </p>
          <div className="app-card">
            <h3>Add a pricing rule</h3>
            <div className="app-form-grid">
              <label className="app-field app-field-wide">
                <span>Zone</span>
                <select
                  className="app-input"
                  value={pricingZoneId}
                  onChange={(e) => setPricingZoneId(e.target.value)}
                >
                  <option value="">Choose a zone…</option>
                  {zones.map((z) => (
                    <option key={z.id} value={z.id}>{z.name}</option>
                  ))}
                </select>
              </label>
              <label className="app-field">
                <span>Standard delivery fee ($)</span>
                <input
                  className="app-input"
                  inputMode="decimal"
                  value={pricingFee}
                  onChange={(e) => setPricingFee(e.target.value)}
                />
              </label>
              <label className="app-field">
                <span>Driver base pay ($)</span>
                <input
                  className="app-input"
                  inputMode="decimal"
                  value={pricingDriverPay}
                  onChange={(e) => setPricingDriverPay(e.target.value)}
                />
              </label>
              <label className="app-field">
                <span>Restaurant fulfillment fee ($)</span>
                <input
                  className="app-input"
                  inputMode="decimal"
                  value={pricingFulfillment}
                  onChange={(e) => setPricingFulfillment(e.target.value)}
                />
              </label>
            </div>
            <button
              type="button"
              className="app-btn"
              disabled={busy === "pricing" || !pricingZoneId}
              onClick={async () => {
                const fee = dollarsToCents(pricingFee);
                const pay = dollarsToCents(pricingDriverPay);
                const fulfil = dollarsToCents(pricingFulfillment);
                if (fee == null || pay == null || fulfil == null) {
                  setError("Enter valid dollar amounts for every field.");
                  return;
                }
                setBusy("pricing");
                setError(null);
                try {
                  await adminCreatePricing({
                    zone_id: pricingZoneId,
                    standard_delivery_fee_cents: fee,
                    driver_base_pay_cents: pay,
                    restaurant_fulfillment_fee_cents: fulfil,
                  });
                  await loadTab("pricing");
                } catch (err) {
                  handleError(err);
                } finally {
                  setBusy(null);
                }
              }}
            >
              Add rule
            </button>
          </div>
          {pricing.length === 0 ? (
            <p>No pricing rules yet.</p>
          ) : (
            <ul className="app-list">
              {pricing.map((rule) => (
                <li key={rule.id} className="app-list-row">
                  <span>
                    <strong>
                      {rule.zone_name ?? rule.name ?? `Rule ${rule.id.slice(0, 8)}`}
                    </strong>
                    <span className="app-list-sub">
                      Delivery fee {formatCents(rule.standard_delivery_fee_cents)}
                      {" · "}Driver pay {formatCents(rule.driver_base_pay_cents)}
                      {" · "}Fulfillment fee{" "}
                      {formatCents(rule.restaurant_fulfillment_fee_cents)}
                    </span>
                  </span>
                  {editingPricing?.id === rule.id ? (
                    <span className="app-actions">
                      <label className="app-field app-field-inline">
                        <span className="app-visually-hidden">
                          New delivery fee in dollars
                        </span>
                        <input
                          className="app-input"
                          inputMode="decimal"
                          value={editFee}
                          onChange={(e) => setEditFee(e.target.value)}
                          placeholder="3.99"
                        />
                      </label>
                      <button
                        type="button"
                        className="app-btn app-btn-small"
                        disabled={busy === rule.id}
                        onClick={async () => {
                          const fee = dollarsToCents(editFee);
                          if (fee == null) {
                            setError("Enter a valid delivery fee.");
                            return;
                          }
                          setBusy(rule.id);
                          setError(null);
                          try {
                            await adminUpdatePricing(rule.id, {
                              standard_delivery_fee_cents: fee,
                            });
                            setEditingPricing(null);
                            await loadTab("pricing");
                          } catch (err) {
                            handleError(err);
                          } finally {
                            setBusy(null);
                          }
                        }}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className="app-btn app-btn-small app-btn-ghost"
                        onClick={() => setEditingPricing(null)}
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="app-btn app-btn-small"
                      onClick={() => {
                        setEditingPricing(rule);
                        setEditFee(
                          rule.standard_delivery_fee_cents != null
                            ? (rule.standard_delivery_fee_cents / 100).toFixed(2)
                            : ""
                        );
                      }}
                    >
                      Edit fee
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "refunds" && (
        <section aria-label="Refunds">
          <h2>Issue a refund</h2>
          <p className="app-lede">
            A full refund moves the order to Refunded and writes offsetting
            ledger entries. Amounts are in dollars; leave the amount blank
            for a full refund.
          </p>
          {refundDone && (
            <p className="app-notice app-notice-good" role="status">
              Refund recorded.
            </p>
          )}
          <div className="app-card">
            <div className="app-form-grid">
              <label className="app-field">
                <span>Order id</span>
                <input
                  className="app-input"
                  value={refundOrderId}
                  onChange={(e) => setRefundOrderId(e.target.value)}
                  placeholder="Order id"
                />
              </label>
              <label className="app-field">
                <span>Amount ($, blank for full)</span>
                <input
                  className="app-input"
                  inputMode="decimal"
                  value={refundAmount}
                  onChange={(e) => setRefundAmount(e.target.value)}
                  placeholder="Full refund"
                />
              </label>
              <label className="app-field app-field-wide">
                <span>Reason</span>
                <input
                  className="app-input"
                  value={refundReason}
                  onChange={(e) => setRefundReason(e.target.value)}
                  placeholder="Why is this refund being issued?"
                />
              </label>
            </div>
            <button
              type="button"
              className="app-btn"
              disabled={busy === "refund"}
              onClick={async () => {
                if (!refundOrderId.trim() || !refundReason.trim()) {
                  setError("Enter an order id and a reason.");
                  return;
                }
                const amount =
                  refundAmount.trim() === ""
                    ? undefined
                    : dollarsToCents(refundAmount);
                if (refundAmount.trim() !== "" && amount == null) {
                  setError("Enter a valid refund amount.");
                  return;
                }
                setBusy("refund");
                setError(null);
                setRefundDone(false);
                try {
                  await createRefund(refundOrderId.trim(), {
                    amount_cents: amount ?? undefined,
                    reason: refundReason.trim(),
                  });
                  setRefundDone(true);
                  setRefundOrderId("");
                  setRefundAmount("");
                  setRefundReason("");
                } catch (err) {
                  handleError(err);
                } finally {
                  setBusy(null);
                }
              }}
            >
              {busy === "refund" ? "Recording…" : "Issue refund"}
            </button>
          </div>
        </section>
      )}

      {tab === "ledger" && (
        <section aria-label="Ledger">
          <h2>Platform ledger</h2>
          <p className="app-lede">
            Append only entries. For every order, total debits equal total
            credits.
          </p>
          {ledger.length === 0 ? (
            <p>No ledger entries yet.</p>
          ) : (
            <div className="app-table-wrap">
              <table className="app-table">
                <thead>
                  <tr>
                    <th>Entry</th>
                    <th>Order</th>
                    <th>Type</th>
                    <th>Direction</th>
                    <th>Amount</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.map((entry) => (
                    <tr key={entry.id}>
                      <td>{entry.id.slice(0, 8)}</td>
                      <td>{entry.order_id?.slice(0, 8) ?? "—"}</td>
                      <td>{entry.type}</td>
                      <td>{entry.direction}</td>
                      <td>{formatCents(entry.amount_cents)}</td>
                      <td>
                        {entry.created_at
                          ? new Date(entry.created_at).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "settlements" && (
        <section aria-label="Settlements">
          <h2>Settlements</h2>
          <p className="app-lede">
            Settlement summaries computed from the ledger. No money moves in
            the slice.
          </p>
          {settlements.length === 0 ? (
            <p>No settlements yet.</p>
          ) : (
            <ul className="app-list">
              {settlements.map((s) => (
                <li key={s.id} className="app-list-row">
                  <span>
                    <strong>
                      {s.restaurant_name ?? `Restaurant ${s.restaurant_id.slice(0, 8)}`}
                    </strong>
                    <span className="app-list-sub">
                      {s.period ?? ""} {s.status ? `· ${s.status}` : ""}
                    </span>
                  </span>
                  <strong>
                    {formatCents(s.payable_cents ?? s.total_cents)}
                  </strong>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "support" && (
        <section aria-label="Support tickets">
          <h2>Support tickets ({tickets.length})</h2>
          {tickets.length === 0 ? (
            <p>No support tickets.</p>
          ) : (
            <ul className="app-list">
              {tickets.map((t) => (
                <li key={t.id} className="app-list-row">
                  <span>
                    <strong>
                      {t.order_id
                        ? `Order ${t.order_id.slice(0, 8)}`
                        : `Ticket ${t.id.slice(0, 8)}`}
                    </strong>
                    <span className="app-list-sub">
                      {t.description ?? "No description"}
                    </span>
                    <span className="app-list-sub">
                      Status: {t.status ?? "open"}
                      {t.created_at
                        ? ` · ${new Date(t.created_at).toLocaleString()}`
                        : ""}
                    </span>
                  </span>
                  {t.status !== "resolved" && (
                    <button
                      type="button"
                      className="app-btn app-btn-small"
                      disabled={busy === t.id}
                      onClick={async () => {
                        setBusy(t.id);
                        setError(null);
                        try {
                          await adminResolveSupport(t.id);
                          await loadTab("support");
                        } catch (err) {
                          handleError(err);
                        } finally {
                          setBusy(null);
                        }
                      }}
                    >
                      Mark resolved
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
