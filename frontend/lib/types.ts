// Shared API types, following docs/mvp-api-contract.md.
// Money is integer cents everywhere. Optional fields stay optional because
// the backend is being built in parallel against the same contract; pages
// read through the helpers in this file so a missing field degrades to a
// blank value instead of a crash.

export type Role =
  | "customer"
  | "restaurant_owner"
  | "restaurant_manager"
  | "restaurant_staff"
  | "driver"
  | "dispatcher"
  | "admin";

export const RESTAURANT_ROLES: Role[] = [
  "restaurant_owner",
  "restaurant_manager",
  "restaurant_staff",
];

export interface RoleAssignment {
  role: Role;
  scope_id?: string | null;
}

export interface User {
  id: string;
  email: string;
  full_name?: string;
  phone?: string | null;
  // The API may return roles as plain strings or as {role, scope_id} rows.
  roles: Array<RoleAssignment | string>;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export type RestaurantStatus =
  | "prospect"
  | "pending"
  | "active"
  | "suspended"
  | "demo";

/** Address as the live API returns it: a nested object with a formatted
 *  line. The flat string form stays supported for older payloads. */
export interface RestaurantAddressObject {
  id?: string | number;
  line1?: string | null;
  line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  formatted?: string | null;
}

export interface RestaurantLocation {
  id?: string | number;
  line1?: string;
  address?: string | RestaurantAddressObject;
  city?: string;
  state?: string;
  postal_code?: string;
  latitude?: number | null;
  longitude?: number | null;
}

export interface Restaurant {
  id: string;
  name: string;
  status: RestaurantStatus;
  source?: string;
  description?: string;
  primary_category?: string;
  price_level?: number | null;
  rating_avg?: number | null;
  rating_count?: number | null;
  website?: string | null;
  phone?: string | null;
  maps_search_url?: string | null;
  locations?: RestaurantLocation[];
  location?: RestaurantLocation | null;
  address?: string | RestaurantAddressObject;
}

export interface Modifier {
  id: string;
  name: string;
  price_cents: number;
}

export interface MenuItem {
  id: string;
  name: string;
  description?: string;
  price_cents: number;
  category?: string;
  available: boolean;
  modifiers?: Modifier[];
}

export type OrderStatus =
  | "PLACED"
  | "ACCEPTED"
  | "PREPARING"
  | "READY"
  | "ASSIGNED"
  | "PICKED_UP"
  | "DELIVERED"
  | "COMPLETED"
  | "REJECTED"
  | "CANCELLED"
  | "REFUNDED"
  | "FAILED";

export interface OrderItem {
  menu_item_id: string;
  name?: string;
  quantity: number;
  unit_price_cents?: number;
  price_cents?: number;
  total_cents?: number;
  // The live API returns top-level order items with snapshot fields.
  name_snapshot?: string;
  price_snapshot_cents?: number;
  line_total_cents?: number;
  modifiers_snapshot?: Array<{ name?: string; price_cents?: number }>;
  modifiers?: Array<{ name: string; price_cents?: number }>;
}

export interface DeliveryAddress {
  line1: string;
  line2?: string;
  city: string;
  state: string;
  postal_code: string;
}

export interface FeeBreakdown {
  subtotal_cents: number;
  delivery_fee_cents: number;
  tax_cents: number;
  tip_cents: number;
  total_cents: number;
  currency?: string;
}

export interface StatusEvent {
  id?: string;
  order_id?: string;
  from_status?: string | null;
  to_status: string;
  actor?: string | null;
  reason?: string | null;
  created_at?: string;
  at?: string;
}

export interface Order {
  id: string;
  restaurant_id: string;
  restaurant_name?: string;
  customer_id?: string;
  customer_name?: string;
  customer_phone?: string;
  status: OrderStatus;
  fulfillment_type: "pickup" | "standard";
  channel: "app" | "direct2door";
  items: OrderItem[];
  subtotal_cents?: number;
  delivery_fee_cents?: number;
  tax_cents?: number;
  tip_cents?: number;
  total_cents?: number;
  checkout_snapshot?: Partial<FeeBreakdown> & {
    items?: OrderItem[];
    restaurant_name?: string;
    fulfillment_type?: string;
    delivery_address?: DeliveryAddress | null;
  };
  delivery_address?: DeliveryAddress | null;
  prep_minutes?: number | null;
  driver_id?: string | null;
  driver_name?: string | null;
  created_at?: string;
  updated_at?: string;
  status_events?: StatusEvent[];
  timeline?: StatusEvent[];
}

export interface Serviceability {
  serviceable: boolean;
  zone_id?: string | null;
  zone_name?: string | null;
  fulfillment_options: Array<"pickup" | "standard">;
}

export interface DeliveryTask {
  id: string;
  task_id?: string;
  order_id: string;
  restaurant_name?: string;
  pickup_address?: string;
  dropoff_address?: string;
  pay_cents: number;
  distance_miles?: number | null;
  eta_minutes?: number | null;
  status?: string;
  created_at?: string;
}

export interface DriverProfile {
  id: string;
  user_id?: string;
  online?: boolean;
  onboarding_status?: string;
  approved?: boolean;
  vehicle?: { make?: string; model?: string; plate?: string } | null;
}

export interface EarningsEntry {
  order_id: string;
  task_id?: string;
  pay_cents: number;
  tip_cents?: number;
  delivered_at?: string;
  created_at?: string;
}

export interface Earnings {
  total_cents?: number;
  total_pay_cents?: number;
  total_tip_cents?: number;
  deliveries?: number;
  entries?: EarningsEntry[];
  items?: EarningsEntry[];
}

export interface DispatchBoard {
  active_orders?: Order[];
  ready_orders?: Order[];
  online_drivers?: Array<{
    id: string;
    name?: string;
    full_name?: string;
    email?: string;
    online?: boolean;
  }>;
}

export interface Zone {
  id: string;
  name: string;
  postal_codes?: string[];
  tax_rate_bps?: number;
  active?: boolean;
  hours?: string | null;
}

export interface PricingRule {
  id: string;
  zone_id?: string;
  zone_name?: string;
  name?: string;
  rule_type?: string;
  standard_delivery_fee_cents?: number;
  driver_base_pay_cents?: number;
  restaurant_fulfillment_fee_cents?: number;
  active?: boolean;
}

export interface AdminMetrics {
  orders_today?: number;
  orders_by_status?: Record<string, number>;
  revenue_cents_today?: number;
  fees_cents_today?: number;
  avg_prep_minutes?: number | null;
  on_time_rate?: number | null;
}

export interface LedgerEntry {
  id: string;
  order_id?: string | null;
  type: string;
  direction: "debit" | "credit";
  amount_cents: number;
  created_at?: string;
}

export interface Settlement {
  id: string;
  restaurant_id: string;
  restaurant_name?: string;
  period?: string;
  total_cents?: number;
  payable_cents?: number;
  status?: string;
}

export interface SupportTicket {
  id: string;
  order_id?: string | null;
  description?: string;
  status?: string;
  created_at?: string;
}

export interface NotificationItem {
  id: string;
  title?: string;
  body?: string;
  message?: string;
  read?: boolean;
  created_at?: string;
}

/** Normalize a user's roles into {role, scope_id} rows. */
export function normalizeRoles(user: User | null): RoleAssignment[] {
  if (!user || !Array.isArray(user.roles)) return [];
  return user.roles.map((r) =>
    typeof r === "string" ? { role: r as Role, scope_id: null } : r
  );
}

export function hasAnyRole(user: User | null, roles: Role[]): boolean {
  const mine = normalizeRoles(user).map((r) => r.role);
  return roles.some((r) => mine.includes(r));
}

/** The restaurant id a restaurant role is scoped to, if any. */
export function restaurantScopeId(user: User | null): string | null {
  const scoped = normalizeRoles(user).find(
    (r) => RESTAURANT_ROLES.includes(r.role) && r.scope_id
  );
  return scoped?.scope_id ?? null;
}

/** Read the authoritative fee breakdown: checkout snapshot first, then
 *  top level order fields. Never invents numbers; missing values are 0. */
export function orderFees(order: Order): FeeBreakdown {
  const snap = order.checkout_snapshot ?? {};
  type NumericFeeKey =
    | "subtotal_cents"
    | "delivery_fee_cents"
    | "tax_cents"
    | "tip_cents"
    | "total_cents";
  const pick = (key: NumericFeeKey): number => {
    const fromSnap = snap[key];
    if (typeof fromSnap === "number") return fromSnap;
    const fromTop = order[key];
    return typeof fromTop === "number" ? fromTop : 0;
  };
  return {
    subtotal_cents: pick("subtotal_cents"),
    delivery_fee_cents: pick("delivery_fee_cents"),
    tax_cents: pick("tax_cents"),
    tip_cents: pick("tip_cents"),
    total_cents: pick("total_cents"),
    currency: snap.currency ?? "USD",
  };
}

/** Status events from whichever field the API populated. */
export function orderEvents(order: Order): StatusEvent[] {
  return order.status_events ?? order.timeline ?? [];
}

/** One display line per ordered item. The live API returns top-level
 *  order items with name_snapshot / price_snapshot_cents, while the
 *  checkout snapshot items carry name / price_cents. Read the snapshot
 *  fields first so real orders never render as "Menu item - $0.00". */
export interface OrderLineItem {
  key: string;
  name: string;
  quantity: number;
  unit_price_cents: number;
  total_cents: number;
  modifiers: string[];
}

export function orderLineItems(order: Order): OrderLineItem[] {
  const names = (mods: Array<{ name?: string }> | undefined): string[] =>
    (mods ?? [])
      .map((m) => m.name)
      .filter((n): n is string => typeof n === "string" && n !== "");
  const top = order.items ?? [];
  if (top.length > 0) {
    return top.map((item, idx) => {
      const unit =
        item.price_snapshot_cents ??
        item.unit_price_cents ??
        item.price_cents ??
        0;
      return {
        key: `${item.menu_item_id}-${idx}`,
        name: item.name_snapshot ?? item.name ?? "Menu item",
        quantity: item.quantity,
        unit_price_cents: unit,
        total_cents:
          item.line_total_cents ?? item.total_cents ?? unit * item.quantity,
        modifiers: names(item.modifiers_snapshot ?? item.modifiers),
      };
    });
  }
  return (order.checkout_snapshot?.items ?? []).map((item, idx) => {
    const unit = item.unit_price_cents ?? item.price_cents ?? 0;
    return {
      key: `${item.menu_item_id}-${idx}`,
      name: item.name ?? "Menu item",
      quantity: item.quantity,
      unit_price_cents: unit,
      total_cents: item.total_cents ?? unit * item.quantity,
      modifiers: names(item.modifiers),
    };
  });
}

/** Short display form of an id. The live API returns integer ids, so a
 *  bare .slice(0, 8) would throw; this coerces first. */
export function shortId(id: string | number | null | undefined): string {
  if (id == null) return "";
  return String(id).slice(0, 8);
}

export function orderDisplayName(order: Order): string {
  return `Order ${shortId(order.id)}`;
}

export function addressLine(a: DeliveryAddress | null | undefined): string {
  if (!a) return "";
  const parts = [a.line1, a.line2, a.city, a.state, a.postal_code].filter(
    (p) => p && p.trim() !== ""
  );
  return parts.join(", ");
}

export function restaurantAddress(r: Restaurant): string {
  const fromObject = (
    a: RestaurantAddressObject | null | undefined
  ): string => {
    if (!a) return "";
    if (a.formatted) return a.formatted;
    return [a.line1, a.line2, a.city, a.state, a.postal_code]
      .filter((p): p is string => typeof p === "string" && p.trim() !== "")
      .join(", ");
  };
  if (typeof r.address === "string" && r.address) return r.address;
  if (r.address && typeof r.address === "object") {
    const built = fromObject(r.address);
    if (built) return built;
  }
  const loc = r.location ?? r.locations?.[0];
  if (!loc) return "";
  if (loc.address && typeof loc.address === "object") {
    return fromObject(loc.address);
  }
  const line =
    loc.line1 ?? (typeof loc.address === "string" ? loc.address : "");
  return [line, loc.city, loc.state, loc.postal_code]
    .filter((p): p is string => typeof p === "string" && p.trim() !== "")
    .join(", ");
}

/** Normalize a list response that may be paginated or a bare array. */
export function asList<T>(value: Paginated<T> | T[] | null | undefined): T[] {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (Array.isArray(value.items)) return value.items;
  return [];
}

export function taskId(task: DeliveryTask): string {
  return task.task_id ?? task.id;
}
