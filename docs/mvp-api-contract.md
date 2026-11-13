# CommonTable MVP Slice — Build Contract

This document is the binding interface contract between the backend, frontend,
and verification workstreams for the MVP slice (spec §16.1). It is written so
the three workstreams can be built in parallel without drifting apart. Where
this document and the Phase 1 spec disagree, the spec wins; where the spec is
silent, this document's choice is the slice decision (recorded here so it is
visible, not hidden in code).

Spec: `../goals/launch-commontable-as-a-live-food-delivery-platform/files/phase-1-production-spec.md`
Repo: `~/workspace/commontable/`

## 1. Global conventions

- API base: `/api/v1`. JSON everywhere. Errors: `{ "error": { "code": "...", "message": "..." } }` with standard HTTP statuses.
- Auth: JWT Bearer (`Authorization: Bearer <access_token>`). Login returns
  `{ access_token, refresh_token, token_type: "bearer", user }`. Access token
  30 min, refresh 7 days (per existing config). WebSocket auth: `?token=<access_token>`
  query param (browsers cannot set WS headers).
- Pagination: `?page=&page_size=` (default 20, max 100). List responses:
  `{ items: [...], page, page_size, total }`.
- Money: **integer cents everywhere**, field names ending in `_cents`, plus
  `"currency": "USD"`. No floats for money. Timestamps: UTC ISO 8601.
- Idempotency: `POST /api/v1/orders` accepts an `Idempotency-Key` header; a
  retried request with the same key + same customer returns the original order,
  never a duplicate.
- Roles: `customer`, `restaurant_owner`, `restaurant_manager`,
  `restaurant_staff`, `driver`, `dispatcher`, `admin`. Restaurant roles are
  scoped to one restaurant via `user_roles.scope_id` (restaurant id).
  Least-privilege server-side enforcement on every endpoint (§4 matrix).
- Copy: clear plain English, avoid dashes in user-facing copy where natural.
  No invented restaurants, metrics, or live claims. Seed data is labeled demo.

## 2. Order state machine (§5)

```
PLACED → ACCEPTED → PREPARING → READY → ASSIGNED → PICKED_UP → DELIVERED → COMPLETED
```

- Pickup orders: `PLACED → ACCEPTED → PREPARING → READY → COMPLETED`
  (no dispatch, no driver, no delivery fee).
- Terminal side states: `REJECTED` (restaurant, with reason), `CANCELLED`
  (customer/restaurant/admin, only from PLACED/ACCEPTED/PREPARING),
  `REFUNDED` (admin refund, full only), `FAILED` (system/admin).
- `ACCEPTED` moves to `PREPARING` automatically on accept (accept confirms
  the prep estimate). `READY` is set explicitly by the restaurant.
- Dispatcher assign moves `READY → ASSIGNED` and creates an offered
  delivery task. Driver decline moves the order back to `READY` (task
  declined) so the dispatcher can reassign. Driver accept keeps `ASSIGNED`.
- Every transition writes a `status_events` row (order, from, to, actor,
  timestamp, reason). The checkout snapshot is written at placement and is
  never mutated afterwards.

## 3. Endpoints (slice subset of spec §10)

### Auth and identity
| Method & path | Role | Notes |
|---|---|---|
| `POST /api/v1/auth/register` | public | Creates an account with a self-service role. Body: email, password, full_name, role (`customer` \| `restaurant_owner` \| `driver`; default `customer`). Other roles are rejected (400); dispatcher/admin are granted by an admin. Driver signup creates a driver profile with onboarding `applied`. Returns user + tokens. |
| `POST /api/v1/auth/login` | public | `{email, password}` → tokens + user. |
| `POST /api/v1/auth/refresh` | public | `{refresh_token}` → new access token. |
| `POST /api/v1/auth/logout` | auth | Revokes the refresh token (jti denylist). |
| `GET /api/v1/users/me` | auth | Profile + roles. |
| `PATCH /api/v1/users/me` | auth | Update full_name / phone. |

### Restaurants and menus
| Method & path | Role | Notes |
|---|---|---|
| `GET /api/v1/restaurants?zone_id=&postal_code=` | public | Only **active** and **demo** restaurants serving the zone/postal code. Prospect (census, unclaimed) restaurants are NEVER listed here and are never orderable. |
| `GET /api/v1/restaurants/{id}` | public | Detail incl. location + hours. Returns 404 for prospect restaurants. |
| `GET /api/v1/restaurants/{id}/menu` | public | Items + modifiers + availability. |
| `GET /api/v1/admin/restaurants?status=` | admin | All restaurants incl. prospects, filterable by status. |
| `POST /api/v1/restaurants` | owner, admin | Creates a `pending` restaurant. |
| `PATCH /api/v1/restaurants/{id}` | owner/manager of it, admin | |
| `POST /api/v1/restaurants/{id}/locations` | owner/manager, admin | |
| `POST /api/v1/restaurants/{id}/menu/items` | owner/manager, admin | |
| `PATCH /api/v1/restaurants/{id}/menu/items/{item_id}` | owner/manager (all fields); staff (availability only); admin | |
| `DELETE /api/v1/restaurants/{id}/menu/items/{item_id}` | owner/manager, admin | Blocked by the DB if the item is on any order. |
| `GET /api/v1/restaurants/{id}/orders` | staff of it, admin | Restaurant order queue + history. |
| `GET /api/v1/restaurants/{id}/reports` | owner/manager, admin | Basic counts + totals + settlement summary. |

### Orders
| Method & path | Role | Notes |
|---|---|---|
| `POST /api/v1/orders` | customer; restaurant staff for `channel: "direct2door"` | Body: restaurant_id, items `[{menu_item_id, quantity, modifiers?}]`, fulfillment_type `pickup` or `standard`, delivery_address `{line1, line2?, city, state, postal_code}` (required for standard), tip_cents (default 0), channel `app` (default) or `direct2door`. Direct2Door staff orders also accept customer_name + customer_phone. Returns the order with the full fee breakdown and checkout snapshot. |
| `GET /api/v1/orders/{id}` | owner customer, restaurant staff of it, dispatcher, admin | Detail + status timeline. |
| `GET /api/v1/orders?status=&restaurant_id=` | scoped by role | Customers see only their own; restaurant staff only theirs; dispatcher/admin all. |
| `POST /api/v1/orders/{id}/accept` | restaurant staff of it | Body: `{prep_minutes}`. → ACCEPTED → PREPARING. |
| `POST /api/v1/orders/{id}/reject` | restaurant staff of it | Body: `{reason}`. → REJECTED. |
| `POST /api/v1/orders/{id}/ready` | restaurant staff of it | → READY. |
| `POST /api/v1/orders/{id}/complete` | restaurant staff of it | Pickup only, from READY → COMPLETED. |
| `POST /api/v1/orders/{id}/cancel` | owner customer, restaurant staff, admin | Body: `{reason}`. Only from PLACED/ACCEPTED/PREPARING. |
| `GET /api/v1/orders/{id}/events` | scoped as order detail | Status-event audit trail. |
| `POST /api/v1/orders/{id}/ratings` | owner customer | After DELIVERED/COMPLETED. `{score 1-5, comment?}`. |

### Dispatch, drivers, deliveries
| Method & path | Role | Notes |
|---|---|---|
| `GET /api/v1/dispatch/serviceability?postal_code=&city=` | public | Returns `{serviceable, zone_id?, zone_name?, fulfillment_options: ["pickup","standard"]}`. Primary check is the zone postal code list; PostGIS point-in-polygon is used when coordinates are supplied and the DB supports it. |
| `GET /api/v1/dispatch/board` | dispatcher, admin | Active orders (PLACED→PICKED_UP), ready signals, online drivers. |
| `POST /api/v1/dispatch/assign` | dispatcher, admin | `{order_id, driver_id}`. Order must be READY. Creates an offered delivery task, order → ASSIGNED. |
| `POST /api/v1/dispatch/override` | dispatcher, admin | `{order_id, driver_id, reason}`. Withdraws the current offer/task, creates a new offer, audit event. |
| `GET /api/v1/drivers/me/offers` | driver | Pending offered tasks with full route + pay shown up front. |
| `GET /api/v1/drivers/me/tasks` | driver | Active tasks (accepted or picked up) — the driver page restores the active delivery from here. |
| `POST /api/v1/drivers/me/offers/{task_id}/accept` | driver | Task → accepted. Order stays ASSIGNED. |
| `POST /api/v1/drivers/me/offers/{task_id}/decline` | driver | Task → declined. Order → READY. |
| `PATCH /api/v1/drivers/me/availability` | driver | `{online: bool}`. Going online requires onboarding `approved` (403 otherwise); going offline is always allowed. |
| `GET /api/v1/drivers/me/earnings` | driver | Per-delivery pay breakdown + totals. |
| `GET /api/v1/drivers/me` | driver | Driver profile incl. onboarding status. |
| `POST /api/v1/deliveries/{task_id}/pickup` | assigned driver | → PICKED_UP. |
| `POST /api/v1/deliveries/{task_id}/deliver` | assigned driver | Body: `{proof_note?}`. → DELIVERED (then COMPLETED by the system). |
| `POST /api/v1/deliveries/{task_id}/issue` | assigned driver | `{description}` → support ticket. |

### Payments, ledger, refunds
| Method & path | Role | Notes |
|---|---|---|
| `POST /api/v1/payments/intent` | customer (own order) | Stub provider only. Returns `{provider: "stub", status: "stub_no_charge", ...}`. The response and all UI copy must make clear **no real payment is processed**. |
| `GET /api/v1/orders/{id}/ledger` | admin; restaurant staff of it (own payable lines) | Ledger entries for the order. |
| `POST /api/v1/orders/{id}/refunds` | admin | `{amount_cents?, reason}`. Writes offsetting entries. Full refund → REFUNDED. |
| `GET /api/v1/admin/settlements?restaurant_id=&period=` | admin | Settlement summaries computed from the ledger (no money movement). |
| `GET /api/v1/admin/ledger` | admin | Platform ledger view, paginated. |

### Admin
| Method & path | Role | Notes |
|---|---|---|
| `GET /api/v1/admin/users` | admin | List users + roles. |
| `GET /api/v1/admin/drivers` | admin | List driver profiles (driver-profile ids, onboarding status). |
| `PATCH /api/v1/admin/users/{id}/roles` | admin | `{add: [...], remove: [...], scope_restaurant_id?}`. |
| `GET /api/v1/admin/zones` / `POST` / `PATCH /api/v1/admin/zones/{id}` | admin | Zone CRUD (name, boundary GeoJSON, postal codes, tax rate, hours, active). |
| `GET /api/v1/admin/pricing` / `POST` / `PATCH /api/v1/admin/pricing/{id}` | admin | Pricing rules by zone (see §5). |
| `GET /api/v1/admin/metrics` | admin | Basic metrics: orders by status, orders today, revenue (fees) today, avg prep, on-time proxy. No invented data; all derived from real rows. |
| `GET /api/v1/admin/support` / `PATCH /api/v1/admin/support/{id}` | admin | Support tickets list + resolve. |
| `POST /api/v1/admin/restaurants/{id}/approve` | admin | pending → active. |
| `POST /api/v1/admin/drivers/{id}/approve` | admin | Driver onboarding approval. |

### Notifications
| Method & path | Role | Notes |
|---|---|---|
| `GET /api/v1/notifications` | auth | Own notifications, newest first. |
| `POST /api/v1/notifications/{id}/read` | auth | Mark one read. |
| `POST /api/v1/notifications/read-all` | auth | Mark all read. |

A notification row is created for the customer on: accepted, preparing,
driver assigned, picked up, delivered. The restaurant gets one on order
placed and order cancelled.

## 4. WebSocket channels (§10.8)

| Channel | Who | Events |
|---|---|---|
| `ws /api/v1/ws/orders/{order_id}?token=` | order customer, restaurant staff of it | `order.status_changed {order_id, from_status, to_status, at}`, `order.driver_assigned {order_id, driver_name}`, `order.eta_updated` |
| `ws /api/v1/ws/driver/{driver_id}?token=` | that driver | `offer.created {task_id, order_id, pay_cents, restaurant_name, pickup_address, dropoff_address, distance_miles?, eta_minutes?}`, `offer.withdrawn {task_id}` |
| `ws /api/v1/ws/dispatch?token=` | dispatcher, admin | `order.placed {order_id}`, `order.ready {order_id}`, `driver.online {driver_id}`, `driver.offline {driver_id}` |
| `ws /api/v1/ws/restaurant/{restaurant_id}?token=` | staff of it | `order.placed {order_id}`, `order.cancelled {order_id}` |

Event envelope: `{ "type": "...", "data": {...}, "at": "<UTC ISO>" }`.
Distance/ETA in offers are estimates from stored address data; when no
routing provider is configured the offer shows the addresses and a clearly
labeled estimate (or "estimate unavailable"), never a fabricated precise
distance. The pay figure is always exact (from pricing rules).

## 5. Pricing defaults (all configurable, all placeholders)

Seeded as `pricing_rules` for the Denton zone. Nothing is hardcoded in
business logic; the admin console can edit every value.

| Rule | Default | Notes |
|---|---|---|
| Standard delivery fee | 399 cents | Blueprint Standard hypothesis ($3.49–$4.99 range); $3.99 is the configured placeholder. |
| Pickup delivery fee | 0 | |
| Driver base pay per delivery | 250 cents | Blueprint illustration value; configurable, auditable. |
| Restaurant fulfillment fee per delivery order | 75 cents | Blueprint illustration value; configurable. |
| Tax rate | 8.25% | Stored on the zone as `tax_rate_bps = 825`. Denton TX sales tax rate; placeholder until confirmed. |

Tax is computed on the food subtotal only (not on the delivery fee or tip),
rounded to the nearest cent. Total = subtotal + delivery fee + tax + tip.

## 6. Ledger model (exact)

Entry types: `customer_charge`, `delivery_cost_expense`,
`restaurant_payable`, `delivery_fee_revenue`, `platform_fee_revenue`,
`driver_payable`, `refund`, `adjustment`. Each entry has a `direction`
(`debit` or `credit`) and integer `amount_cents`. Append-only; balances are
derived, never mutated.

**Invariant (tested): for every order, total debits == total credits.**

Standard delivery order (subtotal S, fee F, tax T, tip Tip, driver pay P,
fulfillment fee FF):
- debit `customer_charge`: S + F + T + Tip
- debit `delivery_cost_expense`: P
- credit `restaurant_payable`: S + T − FF
- credit `delivery_fee_revenue`: F
- credit `platform_fee_revenue`: FF
- credit `driver_payable`: P + Tip

Pickup order:
- debit `customer_charge`: S + T + Tip
- credit `restaurant_payable`: S + T + Tip

Food payment model for the slice: platform-processed (spec G8 allows both
models; the restaurant-processed model is a later per-restaurant setting).
Refunds write offsetting entries (same types, opposite direction) for the
refunded amounts; a full refund moves the order to REFUNDED.

## 7. Data model (slice subset of §9 ERD)

Tables: `users`, `roles`, `user_roles`, `customers`, `restaurants`,
`restaurant_locations`, `menus`, `menu_items`, `modifiers`,
`service_zones`, `addresses`, `orders`, `order_items`, `status_events`,
`payments`, `ledger_entries`, `refunds`, `settlements`, `drivers`,
`driver_vehicles`, `driver_shifts`, `delivery_tasks`, `notifications`,
`integrations`, `pricing_rules`, `support_tickets`, `ratings`,
`revoked_tokens`, `idempotency_keys`.

**Restaurant status** (extended from spec §9 for the census):
`prospect`, `pending`, `active`, `suspended`, `demo`.
- `prospect`: a real Denton restaurant found by the Google Maps census.
  Unclaimed, not onboarded, NOT orderable, never presented as a partner.
- `demo`: the single orderable demo restaurant for the slice (see §8).
- `pending` / `active` / `suspended`: as in the spec.
Only `active` and `demo` restaurants are visible to customers (§3).
`restaurants` carries `place_id` (unique, nullable — Google Maps place id,
the census upsert key), `source` (`census`, `seed`, or `manual`), and
census fields `primary_category`, `price_level`, `rating_avg`,
`rating_count`, `maps_search_url`, `website`. `restaurant_locations`
carries `latitude` / `longitude` floats alongside the PostGIS point.

Deliberately NOT in the slice: `route_batches`, `route_stops` (no batching).
`orders.fulfillment_type` accepts only `pickup` and `standard` in the
slice (the column allows the other values later; the API rejects them now).
`orders.channel` is `app` or `direct2door`.

Geometry: `service_zones.boundary` is a PostGIS polygon (GeoAlchemy2) and
`addresses.location` a PostGIS point, per §9. `service_zones` also carries
`postal_codes` (JSON list) and `tax_rate_bps`, which drive the slice's
serviceability check. Tests run on SQLite (see §9) where the geometry
columns degrade to stored WKT text; no test may depend on PostGIS functions.

## 8. Seed data (all labeled demo)

- Zone: **Denton** (pilot zone). Boundary: rough polygon around Denton TX
  (lng −97.20 to −97.05, lat 33.12 to 33.30). Postal codes: 76201, 76203,
  76205, 76207, 76208, 76209, 76210. Tax 825 bps. Active.
- Restaurant: **Demo Diner (Denton Pilot)** — clearly demo-named. One
  location, one menu, 6 items (one marked unavailable to exercise the
  toggle). Example items: Margherita Pizza 1080, Demo Burger 1099, Garden
  Salad 899, Chicken Sandwich 1199, Fries 399, Iced Tea 299 (cents).
- Demo users, all with password `Demo1234!` (documented in the repo README):
  - `customer@demo.commontable.local` — customer
  - `owner@demo.commontable.local` — restaurant_owner (scoped to Demo Diner)
  - `staff@demo.commontable.local` — restaurant_staff (scoped to Demo Diner)
  - `driver@demo.commontable.local` — driver (approved)
  - `dispatch@demo.commontable.local` — dispatcher
  - `admin@demo.commontable.local` — admin
- Seeding is idempotent (safe to re-run) and lives in `backend/scripts/seed.py`,
  runnable as `python scripts/seed.py` from `backend/` (or via a documented
  equivalent). The seed script never runs automatically on app startup.

### 8.1 Denton restaurant census import

A parallel census (Google Maps) delivers real Denton restaurants as
`data/denton-restaurants.json` at the repo root (schema: `place_id`, `name`,
`address`, `city`/`state`/`zip`, `latitude`/`longitude`, `phone`, `website`,
`primary_category`, `secondary_categories`, `price_level`, `rating_avg`,
`rating_count`, `hours`, `maps_search_url`).
- The backend ships an importer at `backend/scripts/import_denton_restaurants.py`
  that reads that JSON and upserts restaurants **idempotently keyed by
  `place_id`** (re-runs update in place, never duplicate). CLI:
  `--path` (default `../data/denton-restaurants.json`), `--dry-run`.
  It reports counts: created / updated / skipped. Imported restaurants get
  `status: prospect`, `source: census`, one location + address each, no menu.
- The importer normalizes the census data on the way in: ZIP+4 codes are
  truncated to 5 digits; `price_level` labels map to the 1–4 integer scale
  (inexpensive 1, moderate 2, expensive 3, very expensive 4; unknown or
  missing becomes null). Status/source are set to prospect/census ONLY on
  create — a re-import refreshes census fields but never demotes a
  restaurant that has since onboarded.
- Prospects are visible ONLY in the admin console (list + count, with a
  clear "unclaimed, not a partner" label). They never appear in customer
  ordering, search results, or any public page, and no copy anywhere may
  present them as partners.

## 9. Environment notes for builders

- **Docker is NOT available in this build environment.** Do not depend on
  `docker compose` for local verification. The `docker-compose.yml` stays as
  the documented production/local path for machines with Docker.
- Backend tests must run against SQLite via a `DATABASE_URL` override in
  `tests/conftest.py` (e.g. `sqlite:///./test.db` or in-memory). Migrations
  target PostgreSQL/PostGIS; the test suite must not require a live Postgres.
- The coordinator will attempt a real PostgreSQL + PostGIS install during
  integration and run the Alembic migrations against it if available.
- Frontend: no new npm dependencies unless unavoidable (fetch + native
  WebSocket are sufficient). `npm run build` must pass with no backend
  running (all API calls client-side; no SSR fetches to the API).
- Never commit `.env`, secrets, or binaries. Update `.env.example` with any
  new variables (placeholders only).

## 10. Frontend pages (slice)

New routes under the existing Next.js app (keep `/` and `/prototype`
exactly as they are — do not touch them):
- `/login`, `/register`
- `/order` — customer flow: address + serviceability → restaurant list →
  menu/cart → checkout (pickup/Standard, transparent breakdown) → place
- `/order/[id]` — live tracking (WebSocket status updates) + history detail
- `/orders` — customer order history
- `/restaurant` — dashboard: order queue (accept/reject/ready), history
- `/restaurant/menu` — menu item CRUD + availability toggles
- `/restaurant/direct2door` — staff form to record a Direct2Door order
  (creates an order with `channel: "direct2door"` at PLACED)
- `/driver` — availability toggle, offers (route + pay up front),
  accept/decline, active delivery (pickup/deliver), earnings
- `/dispatch` — board (active orders, ready signals, online drivers),
  manual assign + override
- `/admin` — users, restaurants, drivers, zones, pricing, orders, refunds,
  metrics (sections or sub-pages). The restaurants section lists ALL
  restaurants incl. prospects, with status filters and a clear "prospect,
  unclaimed, not a partner" label; prospects are admin-only.
- Shared: `frontend/lib/api.ts` (fetch wrapper, JWT from localStorage,
  base URL from `NEXT_PUBLIC_API_URL`), `frontend/lib/auth.tsx`,
  `frontend/lib/money.ts` (cents formatting), shared components.
- **No-backend behavior:** when the API is unreachable, pages show a clear
  message ("The live ordering service is not connected yet…") and never
  crash. The live Vercel site has no backend yet, so this is the default
  state on the public site.

## 11. File ownership (avoid edit conflicts)

- Backend workstream owns: `backend/**` (except nothing else),
  `.env.example`, `README.md` (setup + demo credentials sections),
  `docker-compose.yml` (only if a fix is needed),
  `data/denton-restaurants.sample.json` (small sample for importer tests).
  The real census file `data/denton-restaurants.json` is delivered by a
  parallel workstream; do not invent a full census file.
- Frontend workstream owns: `frontend/app/order/**`,
  `frontend/app/orders/**`, `frontend/app/restaurant/**`,
  `frontend/app/driver/**`, `frontend/app/dispatch/**`,
  `frontend/app/admin/**`, `frontend/app/login/**`,
  `frontend/app/register/**`, `frontend/lib/**`, `frontend/components/**`,
  `frontend/app/globals.css` (append/extend only).
  It must NOT touch `frontend/app/page.tsx`, `frontend/app/demo.tsx`,
  `frontend/app/prototype/**`, `frontend/app/layout.tsx`,
  `frontend/package.json` (no new deps), `README.md`.
- Verification workstream owns: `scripts/**` (repo root) and
  `docs/build-report.md`.
- Nobody touches: the Muse fullstack artifact `commontable`, `linkedin/`,
  `frontend/public/demo-journey.mp4`, `.gitignore` (unless a new ignore is
  genuinely needed — coordinate first).
