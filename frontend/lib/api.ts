// API client for the CommonTable MVP slice.
// Contract: docs/mvp-api-contract.md. Base URL from NEXT_PUBLIC_API_URL,
// JWT from localStorage attached as Bearer. All calls are client side so
// `npm run build` passes with no backend running.
//
// When the API cannot be reached, apiFetch throws an ApiError with
// `unreachable: true`. Pages must render the offline notice in that case
// and never crash, never show a blank page, and never show fake data.

import type {
  AdminMetrics,
  AuthResponse,
  DeliveryTask,
  DispatchBoard,
  DriverProfile,
  Earnings,
  LedgerEntry,
  MenuItem,
  NotificationItem,
  Order,
  Paginated,
  PricingRule,
  Restaurant,
  Serviceability,
  Settlement,
  StatusEvent,
  SupportTicket,
  User,
  Zone,
} from "./types";

export class ApiError extends Error {
  status?: number;
  code?: string;
  unreachable: boolean;

  constructor(
    message: string,
    opts: { status?: number; code?: string; unreachable?: boolean } = {}
  ) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code;
    this.unreachable = opts.unreachable ?? false;
  }
}

export const OFFLINE_MESSAGE =
  "The live ordering service is not connected yet. Please try again later.";

export function getApiBase(): string {
  const raw = (process.env.NEXT_PUBLIC_API_URL ?? "").trim();
  return raw.replace(/\/+$/, "");
}

export function isApiConfigured(): boolean {
  return getApiBase().length > 0;
}

const ACCESS_KEY = "commontable.access_token";
const REFRESH_KEY = "commontable.refresh_token";
const USER_KEY = "commontable.user";

function storageGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage unavailable; auth still works for this session in memory
    // only if the caller keeps the token, so ignore quietly.
  }
}

function storageRemove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

export function getAccessToken(): string | null {
  return storageGet(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return storageGet(REFRESH_KEY);
}

export function storeTokens(access: string, refresh: string): void {
  storageSet(ACCESS_KEY, access);
  storageSet(REFRESH_KEY, refresh);
}

export function storeUser(user: User): void {
  storageSet(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): User | null {
  const raw = storageGet(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function clearAuthStorage(): void {
  storageRemove(ACCESS_KEY);
  storageRemove(REFRESH_KEY);
  storageRemove(USER_KEY);
}

/** Build a WebSocket URL for a path, deriving ws/wss from the API base. */
export function wsUrl(path: string): string {
  const base = getApiBase();
  const wsBase = base.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");
  return `${wsBase}${path}`;
}

type ApiOptions = RequestInit & {
  idempotencyKey?: string;
  _retried?: boolean;
};

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const res = await fetch(`${getApiBase()}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as {
      access_token: string;
      refresh_token?: string;
    };
    storeTokens(data.access_token, data.refresh_token ?? refresh);
    return true;
  } catch {
    return false;
  }
}

export async function apiFetch<T>(
  path: string,
  options: ApiOptions = {}
): Promise<T> {
  const base = getApiBase();
  if (!base) {
    throw new ApiError(OFFLINE_MESSAGE, { unreachable: true });
  }

  const headers = new Headers(options.headers);
  if (options.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.idempotencyKey) {
    headers.set("Idempotency-Key", options.idempotencyKey);
  }

  let res: Response;
  try {
    const { idempotencyKey: _ignored, _retried: _retriedIgnored, ...rest } =
      options;
    void _ignored;
    void _retriedIgnored;
    res = await fetch(`${base}${path}`, { ...rest, headers });
  } catch {
    throw new ApiError(OFFLINE_MESSAGE, { unreachable: true });
  }

  // Single silent refresh on an expired access token, then one retry.
  if (res.status === 401 && !options._retried && getRefreshToken()) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return apiFetch<T>(path, { ...options, _retried: true });
    }
    clearAuthStorage();
  }

  if (!res.ok) {
    let message = `Request failed (${res.status}).`;
    let code: string | undefined;
    try {
      const body = (await res.json()) as {
        error?: { code?: string; message?: string };
        detail?: string;
      };
      if (body?.error?.message) {
        message = body.error.message;
        code = body.error.code;
      } else if (typeof body?.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the generic message when the body is not JSON.
    }
    throw new ApiError(message, { status: res.status, code });
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function get<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET" });
}

function post<T>(path: string, body?: unknown, extra?: ApiOptions): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
    ...extra,
  });
}

function patch<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PATCH",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function del<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Auth and identity
// ---------------------------------------------------------------------------

export function login(email: string, password: string): Promise<AuthResponse> {
  return post<AuthResponse>("/api/v1/auth/login", { email, password });
}

export function register(
  email: string,
  password: string,
  fullName: string
): Promise<AuthResponse> {
  return post<AuthResponse>("/api/v1/auth/register", {
    email,
    password,
    full_name: fullName,
  });
}

export function logoutRequest(): Promise<void> {
  const refresh = getRefreshToken();
  return post<void>("/api/v1/auth/logout", { refresh_token: refresh });
}

export function fetchMe(): Promise<User> {
  return get<User>("/api/v1/users/me");
}

export function updateMe(body: {
  full_name?: string;
  phone?: string;
}): Promise<User> {
  return patch<User>("/api/v1/users/me", body);
}

// ---------------------------------------------------------------------------
// Restaurants and menus
// ---------------------------------------------------------------------------

export function listRestaurants(postalCode?: string): Promise<Restaurant[]> {
  const q = postalCode
    ? `?postal_code=${encodeURIComponent(postalCode)}`
    : "";
  return get<Paginated<Restaurant> | Restaurant[]>(
    `/api/v1/restaurants${q}`
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function getRestaurant(id: string): Promise<Restaurant> {
  return get<Restaurant>(`/api/v1/restaurants/${id}`);
}

export function getMenu(restaurantId: string): Promise<MenuItem[]> {
  return get<Paginated<MenuItem> | MenuItem[] | { items: MenuItem[] }>(
    `/api/v1/restaurants/${restaurantId}/menu`
  ).then((r) => {
    if (Array.isArray(r)) return r;
    return r.items ?? [];
  });
}

export function createMenuItem(
  restaurantId: string,
  body: {
    name: string;
    description?: string;
    price_cents: number;
    category?: string;
    available?: boolean;
  }
): Promise<MenuItem> {
  return post<MenuItem>(`/api/v1/restaurants/${restaurantId}/menu/items`, body);
}

export function updateMenuItem(
  restaurantId: string,
  itemId: string,
  body: Partial<{
    name: string;
    description: string;
    price_cents: number;
    category: string;
    available: boolean;
  }>
): Promise<MenuItem> {
  return patch<MenuItem>(
    `/api/v1/restaurants/${restaurantId}/menu/items/${itemId}`,
    body
  );
}

export function deleteMenuItem(
  restaurantId: string,
  itemId: string
): Promise<void> {
  return del<void>(
    `/api/v1/restaurants/${restaurantId}/menu/items/${itemId}`
  );
}

export function getRestaurantOrders(restaurantId: string): Promise<Order[]> {
  return get<Paginated<Order> | Order[]>(
    `/api/v1/restaurants/${restaurantId}/orders`
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function getRestaurantReports(restaurantId: string): Promise<{
  orders_today?: number;
  total_orders?: number;
  revenue_cents?: number;
  avg_prep_minutes?: number | null;
  settlement_summary?: unknown;
}> {
  return get(`/api/v1/restaurants/${restaurantId}/reports`);
}

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export interface PlaceOrderBody {
  restaurant_id: string;
  items: Array<{
    menu_item_id: string;
    quantity: number;
    modifiers?: Array<{ modifier_id: string }>;
  }>;
  fulfillment_type: "pickup" | "standard";
  delivery_address?: {
    line1: string;
    line2?: string;
    city: string;
    state: string;
    postal_code: string;
  };
  tip_cents?: number;
  channel?: "app" | "direct2door";
  customer_name?: string;
  customer_phone?: string;
}

export function placeOrder(
  body: PlaceOrderBody,
  idempotencyKey: string
): Promise<Order> {
  return post<Order>("/api/v1/orders", body, { idempotencyKey });
}

export function getOrder(id: string): Promise<Order> {
  return get<Order>(`/api/v1/orders/${id}`);
}

export function getOrderEvents(id: string): Promise<StatusEvent[]> {
  return get<Paginated<StatusEvent> | StatusEvent[]>(
    `/api/v1/orders/${id}/events`
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function listOrders(params?: {
  status?: string;
  restaurant_id?: string;
}): Promise<Order[]> {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.restaurant_id) q.set("restaurant_id", params.restaurant_id);
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return get<Paginated<Order> | Order[]>(`/api/v1/orders${suffix}`).then((r) =>
    Array.isArray(r) ? r : r.items ?? []
  );
}

export function acceptOrder(id: string, prepMinutes: number): Promise<Order> {
  return post<Order>(`/api/v1/orders/${id}/accept`, {
    prep_minutes: prepMinutes,
  });
}

export function rejectOrder(id: string, reason: string): Promise<Order> {
  return post<Order>(`/api/v1/orders/${id}/reject`, { reason });
}

export function readyOrder(id: string): Promise<Order> {
  return post<Order>(`/api/v1/orders/${id}/ready`, {});
}

export function completeOrder(id: string): Promise<Order> {
  return post<Order>(`/api/v1/orders/${id}/complete`, {});
}

export function cancelOrder(id: string, reason: string): Promise<Order> {
  return post<Order>(`/api/v1/orders/${id}/cancel`, { reason });
}

export function rateOrder(
  id: string,
  score: number,
  comment?: string
): Promise<void> {
  return post<void>(`/api/v1/orders/${id}/ratings`, { score, comment });
}

export function createPaymentIntent(orderId: string): Promise<{
  provider: string;
  status: string;
  order_id?: string;
}> {
  return post("/api/v1/payments/intent", { order_id: orderId });
}

export function getOrderLedger(id: string): Promise<LedgerEntry[]> {
  return get<Paginated<LedgerEntry> | LedgerEntry[]>(
    `/api/v1/orders/${id}/ledger`
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function createRefund(
  orderId: string,
  body: { amount_cents?: number; reason: string }
): Promise<unknown> {
  return post(`/api/v1/orders/${orderId}/refunds`, body);
}

// ---------------------------------------------------------------------------
// Dispatch, drivers, deliveries
// ---------------------------------------------------------------------------

export function checkServiceability(
  postalCode: string,
  city: string
): Promise<Serviceability> {
  const q = new URLSearchParams({ postal_code: postalCode, city });
  return get<Serviceability>(`/api/v1/dispatch/serviceability?${q}`);
}

export function getDispatchBoard(): Promise<DispatchBoard> {
  return get<DispatchBoard>("/api/v1/dispatch/board");
}

export function assignOrder(
  orderId: string | number,
  driverId: string | number
): Promise<void> {
  return post<void>("/api/v1/dispatch/assign", {
    order_id: orderId,
    driver_id: driverId,
  });
}

export function overrideAssignment(
  orderId: string | number,
  driverId: string | number,
  reason: string
): Promise<void> {
  return post<void>("/api/v1/dispatch/override", {
    order_id: orderId,
    driver_id: driverId,
    reason,
  });
}

export function getDriverMe(): Promise<DriverProfile> {
  return get<DriverProfile>("/api/v1/drivers/me");
}

export function getDriverOffers(): Promise<DeliveryTask[]> {
  return get<Paginated<DeliveryTask> | DeliveryTask[]>(
    "/api/v1/drivers/me/offers"
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function getDriverTasks(): Promise<DeliveryTask[]> {
  return get<Paginated<DeliveryTask> | DeliveryTask[]>(
    "/api/v1/drivers/me/tasks"
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function acceptOffer(taskId: string): Promise<unknown> {
  return post(`/api/v1/drivers/me/offers/${taskId}/accept`, {});
}

export function declineOffer(taskId: string): Promise<unknown> {
  return post(`/api/v1/drivers/me/offers/${taskId}/decline`, {});
}

export function setDriverAvailability(online: boolean): Promise<DriverProfile> {
  return patch<DriverProfile>("/api/v1/drivers/me/availability", { online });
}

export function getDriverEarnings(): Promise<Earnings> {
  return get<Earnings>("/api/v1/drivers/me/earnings");
}

export function confirmPickup(taskId: string): Promise<unknown> {
  return post(`/api/v1/deliveries/${taskId}/pickup`, {});
}

export function confirmDeliver(
  taskId: string,
  proofNote?: string
): Promise<unknown> {
  return post(`/api/v1/deliveries/${taskId}/deliver`, {
    proof_note: proofNote || undefined,
  });
}

export function reportDeliveryIssue(
  taskId: string,
  description: string
): Promise<unknown> {
  return post(`/api/v1/deliveries/${taskId}/issue`, { description });
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export function adminListUsers(): Promise<User[]> {
  return get<Paginated<User> | User[]>("/api/v1/admin/users").then((r) =>
    Array.isArray(r) ? r : r.items ?? []
  );
}

export function adminUpdateUserRoles(
  userId: string,
  body: { add?: string[]; remove?: string[]; scope_restaurant_id?: string }
): Promise<User> {
  return patch<User>(`/api/v1/admin/users/${userId}/roles`, body);
}

export function adminListRestaurants(status?: string): Promise<Restaurant[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return get<Paginated<Restaurant> | Restaurant[]>(
    `/api/v1/admin/restaurants${q}`
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function adminApproveRestaurant(id: string): Promise<Restaurant> {
  return post<Restaurant>(`/api/v1/admin/restaurants/${id}/approve`, {});
}

export function adminApproveDriver(id: string): Promise<unknown> {
  return post(`/api/v1/admin/drivers/${id}/approve`, {});
}

export function adminListZones(): Promise<Zone[]> {
  return get<Paginated<Zone> | Zone[]>("/api/v1/admin/zones").then((r) =>
    Array.isArray(r) ? r : r.items ?? []
  );
}

export function adminCreateZone(body: {
  name: string;
  postal_codes: string[];
  tax_rate_bps: number;
  active?: boolean;
}): Promise<Zone> {
  return post<Zone>("/api/v1/admin/zones", body);
}

export function adminUpdateZone(
  id: string,
  body: Partial<Zone>
): Promise<Zone> {
  return patch<Zone>(`/api/v1/admin/zones/${id}`, body);
}

export function adminListPricing(): Promise<PricingRule[]> {
  return get<Paginated<PricingRule> | PricingRule[]>(
    "/api/v1/admin/pricing"
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function adminCreatePricing(body: {
  zone_id: string;
  standard_delivery_fee_cents: number;
  driver_base_pay_cents: number;
  restaurant_fulfillment_fee_cents: number;
}): Promise<PricingRule> {
  return post<PricingRule>("/api/v1/admin/pricing", body);
}

export function adminUpdatePricing(
  id: string,
  body: Partial<PricingRule>
): Promise<PricingRule> {
  return patch<PricingRule>(`/api/v1/admin/pricing/${id}`, body);
}

export function adminGetMetrics(): Promise<AdminMetrics> {
  return get<AdminMetrics>("/api/v1/admin/metrics");
}

export function adminListSupport(): Promise<SupportTicket[]> {
  return get<Paginated<SupportTicket> | SupportTicket[]>(
    "/api/v1/admin/support"
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function adminResolveSupport(id: string): Promise<SupportTicket> {
  return patch<SupportTicket>(`/api/v1/admin/support/${id}`, {
    status: "resolved",
  });
}

export function adminListSettlements(restaurantId?: string): Promise<Settlement[]> {
  const q = restaurantId
    ? `?restaurant_id=${encodeURIComponent(restaurantId)}`
    : "";
  return get<Paginated<Settlement> | Settlement[]>(
    `/api/v1/admin/settlements${q}`
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function adminListLedger(): Promise<LedgerEntry[]> {
  return get<Paginated<LedgerEntry> | LedgerEntry[]>(
    "/api/v1/admin/ledger"
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export function listNotifications(): Promise<NotificationItem[]> {
  return get<Paginated<NotificationItem> | NotificationItem[]>(
    "/api/v1/notifications"
  ).then((r) => (Array.isArray(r) ? r : r.items ?? []));
}

export function markNotificationRead(id: string): Promise<void> {
  return post<void>(`/api/v1/notifications/${id}/read`, {});
}

export function markAllNotificationsRead(): Promise<void> {
  return post<void>("/api/v1/notifications/read-all", {});
}
