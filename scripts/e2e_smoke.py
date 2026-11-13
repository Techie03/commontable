#!/usr/bin/env python3
"""CommonTable MVP slice end-to-end smoke test.

Talks to a RUNNING stack over HTTP + WebSocket only. No project imports.
Proves the Phase 1 spec section 16.1 acceptance criteria against the binding
interface contract in docs/mvp-api-contract.md.

Usage:
    pip install -r requirements-smoke.txt
    python e2e_smoke.py

Configuration (environment variables):
    CT_API_URL            Base URL of the API, default http://localhost:8000
    CT_WS_URL             Base URL for WebSockets, default ws://localhost:8000
    CT_DEMO_PASSWORD      Password for all seeded demo accounts, default Demo1234!
    CT_DEMO_OWNER         Owner account email (contract section 8)
    CT_DEMO_STAFF         Restaurant staff account email (contract section 8)
    CT_DEMO_DRIVER        Driver account email (contract section 8)
    CT_DEMO_DISPATCH      Dispatcher account email (contract section 8)
    CT_DEMO_ADMIN         Admin account email (contract section 8)
    CT_DEMO_RESTAURANT    Demo restaurant name, default "Demo Diner"
    CT_POSTAL_OK          Serviceable Denton postal code, default 76201
    CT_POSTAL_BAD         Non-serviceable postal code, default 90210
    CT_HTTP_TIMEOUT       Per-request HTTP timeout in seconds, default 15
    CT_WS_TIMEOUT         Max seconds to wait for WebSocket events, default 45

Exit code: 0 only if every check passes, 1 otherwise, 2 if a required
dependency (httpx / websockets) is missing.

CONTRACT AMBIGUITIES (see also the report back to the coordinator):
  A1. Accept events: contract section 2 says accept moves ACCEPTED to
      PREPARING automatically, but does not say whether one or two
      order.status_changed WebSocket events are emitted. This script
      requires both an ACCEPTED and a PREPARING event, per the task
      brief; if the backend emits only one, the WebSocket check fails
      and reports exactly which event is missing.
  A2. Money field names: contract section 1 says response fields end in
      _cents, but spec section 9 lists bare DB column names (subtotal,
      delivery_fee, ...). This script reads subtotal_cents first and
      falls back to subtotal, and so on for every money field.
  A3. Driver id for dispatch/assign: the contract does not say how a
      dispatcher learns the driver id (drivers table id vs user id).
      This script reads it from GET /api/v1/drivers/me as the driver,
      falling back to scanning the dispatch board payload.
  A4. Offer pay field: the WS offer.created event uses pay_cents, the
      delivery_tasks column is offered_pay, and the REST offers
      endpoint field name is unspecified. This script accepts
      pay_cents, offered_pay, offered_pay_cents, or pay.
  A5. Tax rounding: "rounded to the nearest cent" does not say half-up
      or banker's rounding. This script uses half-up and allows a
      1 cent tolerance on the tax line.
  A6. Price changes: the brief says "as restaurant staff, change a menu
      item price", but contract sections 3-4 restrict staff to
      availability-only changes; price changes need owner/manager.
      This script uses the OWNER account for the price change and
      separately asserts that a staff price change is rejected (403).
  A7. Dispatch board shape: no response schema is given for
      GET /api/v1/dispatch/board. This script searches the payload
      recursively for the order id and driver ids.
  A8. Ledger envelope: list vs paginated {items} is unspecified, and
      the entry type field is entry_type per spec section 9 (this
      script also accepts "type"). Both shapes are handled.
  A9. Menu envelope: {items} vs a bare list is unspecified. Both are
      handled.
 A10. Order placement success status (200 vs 201) is unspecified. Both
      are accepted.
 A11. Whether public restaurant list items include a status field is
      unspecified. Prospect exclusion is verified by cross-checking
      ids/names against the admin prospect list when status is absent.
 A12. Deliver transition: contract section 3 says deliver moves the
      order to DELIVERED "then COMPLETED by the system"; whether a
      second status_changed event to COMPLETED is emitted, and when,
      is unspecified. This script accepts DELIVERED or COMPLETED as
      the final order status and only requires the DELIVERED event.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from decimal import Decimal, ROUND_HALF_UP

try:
    import httpx
except ImportError:  # pragma: no cover - handled at startup
    httpx = None

try:
    from websockets.asyncio.client import connect as ws_connect
except ImportError:  # pragma: no cover - fallback for older websockets
    try:
        from websockets import connect as ws_connect  # type: ignore[no-redef]
    except ImportError:
        ws_connect = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = os.environ.get("CT_API_URL", "http://localhost:8000").rstrip("/")
WS_URL = os.environ.get("CT_WS_URL", "ws://localhost:8000").rstrip("/")
DEMO_PASSWORD = os.environ.get("CT_DEMO_PASSWORD", "Demo1234!")
DEMO_OWNER = os.environ.get("CT_DEMO_OWNER", "owner@demo.commontable.local")
DEMO_STAFF = os.environ.get("CT_DEMO_STAFF", "staff@demo.commontable.local")
DEMO_DRIVER = os.environ.get("CT_DEMO_DRIVER", "driver@demo.commontable.local")
DEMO_DISPATCH = os.environ.get("CT_DEMO_DISPATCH", "dispatch@demo.commontable.local")
DEMO_ADMIN = os.environ.get("CT_DEMO_ADMIN", "admin@demo.commontable.local")
DEMO_RESTAURANT = os.environ.get("CT_DEMO_RESTAURANT", "Demo Diner")
POSTAL_OK = os.environ.get("CT_POSTAL_OK", "76201")
POSTAL_BAD = os.environ.get("CT_POSTAL_BAD", "90210")
HTTP_TIMEOUT = float(os.environ.get("CT_HTTP_TIMEOUT", "15"))
WS_TIMEOUT = float(os.environ.get("CT_WS_TIMEOUT", "45"))

# Seeded pricing defaults from contract section 5. These are configurable
# pricing rules, not hardcoded business logic; the script asserts the seeded
# defaults and says so in its output if they differ.
EXPECTED_DELIVERY_FEE_CENTS = int(os.environ.get("CT_DELIVERY_FEE_CENTS", "399"))
TAX_RATE_BPS = int(os.environ.get("CT_TAX_RATE_BPS", "825"))
DRIVER_BASE_PAY_CENTS = int(os.environ.get("CT_DRIVER_BASE_PAY_CENTS", "250"))
FULFILLMENT_FEE_CENTS = int(os.environ.get("CT_FULFILLMENT_FEE_CENTS", "75"))

TIP_CENTS = 200
PREP_MINUTES = 20

REQUIRED_WS_STATUSES = [
    "ACCEPTED",
    "PREPARING",
    "READY",
    "ASSIGNED",
    "PICKED_UP",
    "DELIVERED",
]

LEDGER_ENTRY_TYPES = {
    "customer_charge",
    "delivery_cost_expense",
    "restaurant_payable",
    "delivery_fee_revenue",
    "platform_fee_revenue",
    "driver_payable",
}


# ---------------------------------------------------------------------------
# Check recording
# ---------------------------------------------------------------------------


class Recorder:
    """Collects one PASS/FAIL/SKIP line per check and prints a summary."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.n = 0

    def _line(self, outcome: str, name: str, detail: str = "") -> None:
        self.n += 1
        suffix = f" -- {detail}" if detail else ""
        print(f"[{outcome}] {self.n:02d}. {name}{suffix}", flush=True)

    def ok(self, name: str, detail: str = "") -> None:
        self.passed += 1
        self._line("PASS", name, detail)

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        self._line("FAIL", name, detail)

    def skip(self, name: str, detail: str = "") -> None:
        self.skipped += 1
        self._line("SKIP", name, detail)

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, detail)
        return condition

    def summary(self) -> bool:
        total = self.passed + self.failed + self.skipped
        print()
        print(
            f"Summary: {self.passed} passed, {self.failed} failed, "
            f"{self.skipped} skipped (of {total} checks)"
        )
        if self.failed == 0 and self.skipped == 0:
            print("SMOKE TEST: PASS")
            return True
        print("SMOKE TEST: FAIL")
        return False


# ---------------------------------------------------------------------------
# Small helpers for underspecified response shapes (see ambiguities above)
# ---------------------------------------------------------------------------


def as_items(payload):
    """Accept a bare list or a paginated {items: [...]} envelope."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return items
    return []


def money(obj: dict, base: str):
    """Read a money field, preferring <base>_cents, falling back to <base>."""
    if not isinstance(obj, dict):
        return None
    if f"{base}_cents" in obj:
        return obj[f"{base}_cents"]
    return obj.get(base)


def expected_tax_cents(subtotal_cents: int) -> int:
    """Tax on the food subtotal only, rounded half-up to the nearest cent."""
    tax = (Decimal(subtotal_cents) * Decimal(TAX_RATE_BPS) / Decimal(10000)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(tax)


def find_string(payload, needle) -> bool:
    """True if needle appears anywhere in a JSON payload (recursive).

    Matches scalar values by equality or string form, so integer ids
    (e.g. an order id of 1) are found as well as strings.
    """
    if isinstance(payload, dict):
        return any(find_string(v, needle) for v in payload.values())
    if isinstance(payload, list):
        return any(find_string(v, needle) for v in payload)
    if payload is None:
        return False
    return payload == needle or str(payload) == str(needle)


def find_driver_id(payload):
    """Best-effort extraction of a driver id from a board-style payload."""
    if isinstance(payload, dict):
        for key in ("drivers", "online_drivers", "available_drivers"):
            drivers = payload.get(key)
            if isinstance(drivers, list) and drivers:
                first = drivers[0]
                if isinstance(first, dict):
                    return first.get("driver_id") or first.get("id")
                return first
        for value in payload.values():
            found = find_driver_id(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = find_driver_id(item)
            if found:
                return found
    return None


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


class Api:
    def __init__(self, client: "httpx.AsyncClient") -> None:
        self.client = client

    async def call(self, method: str, path: str, token=None, **kwargs):
        """Returns (status_code, parsed_json_or_text). Never raises on HTTP
        error statuses; raises only on transport failure."""
        headers = dict(kwargs.pop("headers", {}) or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = await self.client.request(
            method, f"{API_URL}{path}", headers=headers, **kwargs
        )
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        return resp.status_code, body

    async def login(self, email: str, password: str):
        status, body = await self.call(
            "POST", "/api/v1/auth/login", json={"email": email, "password": password}
        )
        if status != 200 or not isinstance(body, dict) or not body.get("access_token"):
            return None, status, body
        return body["access_token"], status, body


# ---------------------------------------------------------------------------
# WebSocket collector
# ---------------------------------------------------------------------------


async def collect_ws_events(url: str, events: list, stop: asyncio.Event) -> None:
    """Connects to a WS channel and appends parsed messages to events until
    stop is set. Records a ('__error__', message) tuple on failure."""
    try:
        async with ws_connect(url) as ws:
            while not stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    events.append(json.loads(raw))
                except ValueError:
                    events.append({"type": "__unparsed__", "raw": raw})
    except Exception as exc:  # noqa: BLE001 - surfaced as a check failure
        events.append({"type": "__error__", "data": {"message": str(exc)}})


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


async def main() -> int:
    rec = Recorder()
    run_id = uuid.uuid4().hex[:8]
    print(f"CommonTable MVP smoke test (run {run_id})")
    print(f"API: {API_URL}   WS: {WS_URL}")
    print()

    if httpx is None or ws_connect is None:
        missing = []
        if httpx is None:
            missing.append("httpx")
        if ws_connect is None:
            missing.append("websockets")
        print(
            "Missing required dependencies: "
            + ", ".join(missing)
            + ". Install them with: pip install -r requirements-smoke.txt"
        )
        return 2

    state: dict = {}

    # trust_env=False: the smoke test talks directly to CT_API_URL (localhost
    # by default) and must not pick up proxy settings from the environment,
    # which can contain entries httpx cannot parse.
    try:
        client = httpx.AsyncClient(timeout=HTTP_TIMEOUT, trust_env=False)
    except Exception as exc:  # noqa: BLE001
        rec.fail("Backend is up (GET /health)", f"could not start HTTP client: {exc}")
        rec.summary()
        return 1

    async with client:
        api = Api(client)

        # -- 1. Backend health ------------------------------------------------
        try:
            status, body = await api.call("GET", "/health")
            rec.check(
                "Backend is up (GET /health)",
                status == 200,
                f"status {status}, body {body}" if status != 200 else f"body {body}",
            )
            if status != 200:
                print("Backend is not up; cannot continue.")
                return 1 if not rec.summary() else 0
        except Exception as exc:  # noqa: BLE001
            rec.fail("Backend is up (GET /health)", f"request failed: {exc}")
            rec.summary()
            return 1

        # -- 2. Register and log in a fresh customer --------------------------
        customer_email = f"smoke-{run_id}@example.com"
        customer_password = "Smoke1234!"
        customer_token = None
        try:
            status, body = await api.call(
                "POST",
                "/api/v1/auth/register",
                json={
                    "email": customer_email,
                    "password": customer_password,
                    "full_name": "Smoke Test Customer",
                },
            )
            ok = status in (200, 201) and isinstance(body, dict)
            rec.check(
                "Register a fresh customer",
                ok,
                f"email {customer_email}, status {status}"
                + ("" if ok else f", body {body}"),
            )
            if ok and body.get("access_token"):
                customer_token = body["access_token"]
        except Exception as exc:  # noqa: BLE001
            rec.fail("Register a fresh customer", f"request failed: {exc}")

        if customer_token is None:
            try:
                customer_token, status, body = await api.login(
                    customer_email, customer_password
                )
                rec.check(
                    "Log in as the fresh customer",
                    customer_token is not None,
                    f"status {status}" + ("" if customer_token else f", body {body}"),
                )
            except Exception as exc:  # noqa: BLE001
                rec.fail("Log in as the fresh customer", f"request failed: {exc}")
        else:
            rec.ok(
                "Log in as the fresh customer",
                "register returned tokens, login step covered by register",
            )

        # Second fresh customer, used only for the cross-user RBAC check.
        customer_b_email = f"smoke-b-{run_id}@example.com"
        customer_b_token = None
        try:
            status, body = await api.call(
                "POST",
                "/api/v1/auth/register",
                json={
                    "email": customer_b_email,
                    "password": customer_password,
                    "full_name": "Smoke Test Customer B",
                },
            )
            if isinstance(body, dict) and body.get("access_token"):
                customer_b_token = body["access_token"]
            if customer_b_token is None:
                customer_b_token, _, _ = await api.login(
                    customer_b_email, customer_password
                )
            rec.check(
                "Register a second fresh customer (RBAC check)",
                customer_b_token is not None,
                f"email {customer_b_email}, status {status}",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Register a second fresh customer (RBAC check)", str(exc))

        # -- 3. Log in as the seeded demo accounts (contract section 8) -------
        tokens = {}
        for label, email in [
            ("owner", DEMO_OWNER),
            ("staff", DEMO_STAFF),
            ("driver", DEMO_DRIVER),
            ("dispatch", DEMO_DISPATCH),
            ("admin", DEMO_ADMIN),
        ]:
            try:
                token, status, body = await api.login(email, DEMO_PASSWORD)
                tokens[label] = token
                rec.check(
                    f"Log in as demo {label} ({email})",
                    token is not None,
                    f"status {status}" + ("" if token else f", body {body}"),
                )
            except Exception as exc:  # noqa: BLE001
                tokens[label] = None
                rec.fail(f"Log in as demo {label} ({email})", f"request failed: {exc}")

        owner_token = tokens.get("owner")
        staff_token = tokens.get("staff")
        driver_token = tokens.get("driver")
        dispatch_token = tokens.get("dispatch")
        admin_token = tokens.get("admin")

        # -- 4. Serviceability -------------------------------------------------
        try:
            status, body = await api.call(
                "GET", f"/api/v1/dispatch/serviceability?postal_code={POSTAL_OK}"
            )
            options = body.get("fulfillment_options", []) if isinstance(body, dict) else []
            rec.check(
                f"Serviceability: Denton postal code {POSTAL_OK} is serviceable",
                status == 200
                and isinstance(body, dict)
                and body.get("serviceable") is True
                and "standard" in options
                and "pickup" in options,
                f"status {status}, body {body}",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail(f"Serviceability: Denton postal code {POSTAL_OK}", str(exc))

        try:
            status, body = await api.call(
                "GET", f"/api/v1/dispatch/serviceability?postal_code={POSTAL_BAD}"
            )
            rec.check(
                f"Serviceability: non-Denton postal code {POSTAL_BAD} is not serviceable",
                status == 200
                and isinstance(body, dict)
                and body.get("serviceable") is False,
                f"status {status}, body {body}",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail(f"Serviceability: non-Denton postal code {POSTAL_BAD}", str(exc))

        # -- 5. Public restaurant list: only demo/active, no prospects --------
        public_restaurants = []
        demo_restaurant = None
        try:
            status, body = await api.call(
                "GET", f"/api/v1/restaurants?postal_code={POSTAL_OK}"
            )
            public_restaurants = as_items(body)
            statuses = [
                r.get("status") for r in public_restaurants if isinstance(r, dict)
            ]
            has_status_field = any(s is not None for s in statuses)
            prospect_in_list = any(s == "prospect" for s in statuses)
            if has_status_field:
                rec.check(
                    "Public restaurant list contains no prospects",
                    not prospect_in_list,
                    f"{len(public_restaurants)} restaurants listed, "
                    f"statuses seen: {sorted(set(statuses))}",
                )
            else:
                # Ambiguity A11: verified later by cross-checking against the
                # admin prospect list (see the census check at the end).
                rec.ok(
                    "Public restaurant list contains no prospects",
                    "status field not exposed in public list; verified by "
                    "cross-check against the admin prospect list below",
                )
            for r in public_restaurants:
                if not isinstance(r, dict):
                    continue
                if r.get("status") == "demo" or DEMO_RESTAURANT.lower() in str(
                    r.get("name", "")
                ).lower():
                    demo_restaurant = r
                    break
            rec.check(
                f"Demo restaurant '{DEMO_RESTAURANT}' is listed",
                demo_restaurant is not None,
                f"{len(public_restaurants)} restaurants listed"
                + (
                    f", demo id {demo_restaurant.get('id')}"
                    if demo_restaurant
                    else ", names seen: "
                    + ", ".join(str(r.get('name')) for r in public_restaurants[:5])
                ),
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Public restaurant list", f"request failed: {exc}")

        if demo_restaurant is None:
            rec.skip("Demo menu loads", "no demo restaurant found")
            rec.skip("Place a Standard delivery order", "no demo restaurant found")
            print()
            print("No demo restaurant; the ordering checks cannot run.")
            rec.summary()
            return 1

        demo_id = demo_restaurant.get("id")
        state["demo_id"] = demo_id

        # -- 6. Demo menu ------------------------------------------------------
        menu_items = []
        try:
            status, body = await api.call(
                "GET", f"/api/v1/restaurants/{demo_id}/menu"
            )
            menu_items = as_items(body)
            if not menu_items and isinstance(body, dict):
                # Some APIs nest items under menus: [{items: [...]}].
                for menu in as_items(body.get("menus", [])):
                    menu_items.extend(as_items(menu.get("items", [])))
            available = [
                i
                for i in menu_items
                if isinstance(i, dict) and i.get("available", True) is not False
            ]
            state["available_items"] = available
            rec.check(
                "Demo menu loads with available items",
                status == 200 and len(available) >= 1,
                f"status {status}, {len(menu_items)} items, "
                f"{len(available)} available",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Demo menu loads with available items", f"request failed: {exc}")

        available = state.get("available_items", [])
        if not available or customer_token is None:
            rec.skip("Place a Standard delivery order", "no menu items or no customer login")
            print()
            print("Cannot place an order; stopping the ordering checks here.")
            rec.summary()
            return 1

        # Pick two available items (or one item, quantity 2) for the order.
        chosen = available[:2]
        order_items = [
            {"menu_item_id": item["id"], "quantity": 1} for item in chosen
        ]
        subtotal = sum(
            (money(item, "price") or 0) * 1 for item in chosen
        )
        state["subtotal"] = subtotal
        state["chosen_items"] = chosen

        # -- 7. Place a Standard delivery order (with Idempotency-Key) --------
        idempotency_key = f"smoke-{run_id}-delivery"
        delivery_order = None
        delivery_address = {
            "line1": "123 W Hickory St",
            "city": "Denton",
            "state": "TX",
            "postal_code": POSTAL_OK,
        }
        order_body = {
            "restaurant_id": demo_id,
            "items": order_items,
            "fulfillment_type": "standard",
            "delivery_address": delivery_address,
            "tip_cents": TIP_CENTS,
            "channel": "app",
        }
        try:
            status, body = await api.call(
                "POST",
                "/api/v1/orders",
                token=customer_token,
                json=order_body,
                headers={"Idempotency-Key": idempotency_key},
            )
            ok = status in (200, 201) and isinstance(body, dict) and body.get("id")
            if ok:
                delivery_order = body
            rec.check(
                "Place a Standard delivery order",
                ok,
                f"status {status}"
                + (f", order id {body.get('id')}" if ok else f", body {body}"),
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Place a Standard delivery order", f"request failed: {exc}")

        if delivery_order is None:
            rec.skip("Fee breakdown matches the contract defaults", "no order placed")
            rec.skip("Checkout snapshot is present on the order", "no order placed")
            rec.skip("Idempotent re-POST returns the same order", "no order placed")
            rec.skip("Live WebSocket status updates", "no order placed")
            print()
            print("No delivery order; the live-loop checks cannot run.")
            rec.summary()
            return 1

        order_id = delivery_order["id"]
        state["order_id"] = order_id

        # -- 8. Fee breakdown --------------------------------------------------
        got_subtotal = money(delivery_order, "subtotal")
        got_fee = money(delivery_order, "delivery_fee")
        got_tax = money(delivery_order, "tax")
        got_tip = money(delivery_order, "tip")
        got_total = money(delivery_order, "total")
        want_tax = expected_tax_cents(subtotal)
        want_total = subtotal + EXPECTED_DELIVERY_FEE_CENTS + want_tax + TIP_CENTS
        breakdown_detail = (
            f"subtotal {got_subtotal} (expected {subtotal}), "
            f"fee {got_fee} (expected {EXPECTED_DELIVERY_FEE_CENTS}), "
            f"tax {got_tax} (expected {want_tax} at 8.25%), "
            f"tip {got_tip} (expected {TIP_CENTS}), "
            f"total {got_total} (expected {want_total})"
        )
        tax_ok = got_tax is not None and abs(got_tax - want_tax) <= 1  # see A5
        total_ok = (
            got_subtotal is not None
            and got_fee is not None
            and got_tax is not None
            and got_tip is not None
            and got_total is not None
            and got_total == got_subtotal + got_fee + got_tax + got_tip
        )
        rec.check(
            "Fee breakdown matches the contract defaults",
            got_subtotal == subtotal
            and got_fee == EXPECTED_DELIVERY_FEE_CENTS
            and tax_ok
            and got_tip == TIP_CENTS
            and total_ok,
            breakdown_detail
            + (
                ""
                if got_fee == EXPECTED_DELIVERY_FEE_CENTS
                else " (delivery fee is a configurable pricing rule; "
                "a different value means the seed differs, not "
                "necessarily a bug)"
            ),
        )

        # -- 9. Checkout snapshot ----------------------------------------------
        snapshot = delivery_order.get("checkout_snapshot")
        rec.check(
            "Checkout snapshot is present on the order",
            isinstance(snapshot, dict) and len(snapshot) > 0,
            f"snapshot keys: {sorted(snapshot.keys())}"
            if isinstance(snapshot, dict)
            else f"snapshot value: {snapshot!r}",
        )
        state["snapshot_before"] = snapshot
        state["totals_before"] = {
            "subtotal": got_subtotal,
            "delivery_fee": got_fee,
            "tax": got_tax,
            "tip": got_tip,
            "total": got_total,
        }

        # -- 10. Idempotency: same key returns the same order ------------------
        try:
            status, body = await api.call(
                "POST",
                "/api/v1/orders",
                token=customer_token,
                json=order_body,
                headers={"Idempotency-Key": idempotency_key},
            )
            same = (
                isinstance(body, dict) and body.get("id") == order_id
            )
            rec.check(
                "Idempotent re-POST returns the same order (no duplicate)",
                same,
                f"status {status}, first id {order_id}, "
                f"second id {body.get('id') if isinstance(body, dict) else body}",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Idempotent re-POST returns the same order", str(exc))

        # -- 11. Live updates: open the WS channel BEFORE the restaurant acts -
        ws_events: list = []
        ws_stop = asyncio.Event()
        ws_url = f"{WS_URL}/api/v1/ws/orders/{order_id}?token={customer_token}"
        ws_task = asyncio.create_task(collect_ws_events(ws_url, ws_events, ws_stop))
        # Give the socket a moment to connect before driving the loop.
        await asyncio.sleep(1.0)
        ws_error = next(
            (e for e in ws_events if e.get("type") == "__error__"), None
        )
        rec.check(
            "WebSocket connects to the order channel as the customer",
            ws_error is None,
            f"channel /api/v1/ws/orders/{order_id}"
            + (f", error: {ws_error['data']}" if ws_error else ""),
        )

        # -- 12. Restaurant accepts, then marks ready --------------------------
        async def transition(name, method, path, token, body=None):
            try:
                status, resp = await api.call(method, path, token=token, json=body)
                ok = status in (200, 201)
                new_status = resp.get("status") if isinstance(resp, dict) else None
                rec.check(
                    name,
                    ok,
                    f"status {status}"
                    + (f", order status now {new_status}" if ok else f", body {resp}"),
                )
                return ok, new_status
            except Exception as exc:  # noqa: BLE001
                rec.fail(name, f"request failed: {exc}")
                return False, None

        await transition(
            "Restaurant accepts the order with a prep estimate",
            "POST",
            f"/api/v1/orders/{order_id}/accept",
            staff_token,
            {"prep_minutes": PREP_MINUTES},
        )
        await asyncio.sleep(0.5)
        await transition(
            "Restaurant marks the order ready",
            "POST",
            f"/api/v1/orders/{order_id}/ready",
            staff_token,
        )
        await asyncio.sleep(0.5)

        # -- 13. Dispatcher board + manual assign ------------------------------
        board_body = None
        try:
            status, body = await api.call(
                "GET", "/api/v1/dispatch/board", token=dispatch_token
            )
            board_body = body
            rec.check(
                "Dispatcher board lists the order",
                status == 200 and find_string(body, order_id),
                f"status {status}"
                + (
                    ""
                    if status == 200 and find_string(body, order_id)
                    else f", body {str(body)[:300]}"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Dispatcher board lists the order", f"request failed: {exc}")

        # Resolve the demo driver id (ambiguity A3).
        driver_id = None
        try:
            status, body = await api.call(
                "GET", "/api/v1/drivers/me", token=driver_token
            )
            if isinstance(body, dict):
                driver_id = body.get("id") or body.get("driver_id")
            rec.check(
                "Driver profile returns a driver id",
                driver_id is not None,
                f"status {status}, driver id {driver_id}",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Driver profile returns a driver id", f"request failed: {exc}")
        if driver_id is None and board_body is not None:
            driver_id = find_driver_id(board_body)
            if driver_id:
                print(f"    (driver id recovered from the dispatch board: {driver_id})")

        # Driver goes online so the assignment has an available driver.
        try:
            status, body = await api.call(
                "PATCH",
                "/api/v1/drivers/me/availability",
                token=driver_token,
                json={"online": True},
            )
            rec.check(
                "Driver goes online",
                status in (200, 201),
                f"status {status}" + ("" if status in (200, 201) else f", body {body}"),
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Driver goes online", f"request failed: {exc}")

        assigned = False
        if driver_id is None:
            rec.skip(
                "Dispatcher manually assigns the demo driver",
                "no driver id could be resolved",
            )
        else:
            try:
                status, body = await api.call(
                    "POST",
                    "/api/v1/dispatch/assign",
                    token=dispatch_token,
                    json={"order_id": order_id, "driver_id": driver_id},
                )
                assigned = status in (200, 201)
                rec.check(
                    "Dispatcher manually assigns the demo driver",
                    assigned,
                    f"status {status}, driver {driver_id}"
                    + ("" if assigned else f", body {body}"),
                )
            except Exception as exc:  # noqa: BLE001
                rec.fail("Dispatcher manually assigns the demo driver", str(exc))
        await asyncio.sleep(0.5)

        # -- 14. Driver offers, accept, pickup, deliver ------------------------
        task_id = None
        try:
            status, body = await api.call(
                "GET", "/api/v1/drivers/me/offers", token=driver_token
            )
            offers = as_items(body)
            mine = [
                o
                for o in offers
                if isinstance(o, dict) and o.get("order_id") == order_id
            ]
            pay = None
            if mine:
                task_id = mine[0].get("id") or mine[0].get("task_id")
                for key in ("pay_cents", "offered_pay", "offered_pay_cents", "pay"):
                    if mine[0].get(key) is not None:
                        pay = (key, mine[0][key])
                        break
            rec.check(
                "Driver offer shows the pay before accept",
                len(mine) >= 1 and pay is not None and pay[1] is not None,
                f"status {status}, {len(offers)} offers, "
                + (
                    f"pay shown as {pay[0]}={pay[1]}"
                    if pay
                    else "no pay field found on the offer"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Driver offer shows the pay before accept", str(exc))

        if task_id is None:
            rec.skip("Driver accepts the offer", "no delivery task id found")
            rec.skip("Driver confirms pickup", "no delivery task id found")
            rec.skip("Driver confirms delivery", "no delivery task id found")
        else:
            await transition(
                "Driver accepts the offer",
                "POST",
                f"/api/v1/drivers/me/offers/{task_id}/accept",
                driver_token,
            )
            await asyncio.sleep(0.5)
            await transition(
                "Driver confirms pickup",
                "POST",
                f"/api/v1/deliveries/{task_id}/pickup",
                driver_token,
            )
            await asyncio.sleep(0.5)
            await transition(
                "Driver confirms delivery",
                "POST",
                f"/api/v1/deliveries/{task_id}/deliver",
                driver_token,
                {"proof_note": "Smoke test delivery"},
            )

        # -- 15. Evaluate the WebSocket events ---------------------------------
        # Wait until all expected events arrive or the timeout expires.
        deadline = asyncio.get_running_loop().time() + WS_TIMEOUT
        while asyncio.get_running_loop().time() < deadline:
            seen = {
                e.get("data", {}).get("to_status")
                for e in ws_events
                if e.get("type") == "order.status_changed"
            }
            if all(s in seen for s in REQUIRED_WS_STATUSES):
                break
            await asyncio.sleep(1.0)
        ws_stop.set()
        try:
            await asyncio.wait_for(ws_task, timeout=5.0)
        except asyncio.TimeoutError:
            ws_task.cancel()

        seen_statuses = [
            e.get("data", {}).get("to_status")
            for e in ws_events
            if e.get("type") == "order.status_changed"
        ]
        seen_set = set(seen_statuses)
        missing = [s for s in REQUIRED_WS_STATUSES if s not in seen_set]
        arrived = [s for s in REQUIRED_WS_STATUSES if s in seen_set]
        rec.check(
            "Live updates: customer receives every status event",
            not missing,
            f"arrived: {arrived if arrived else 'none'}; "
            f"missing: {missing if missing else 'none'}; "
            f"all status events in order: {seen_statuses}",
        )

        # Final order status after delivery.
        try:
            status, body = await api.call(
                "GET", f"/api/v1/orders/{order_id}", token=customer_token
            )
            final_status = body.get("status") if isinstance(body, dict) else None
            rec.check(
                "Order ends DELIVERED (or COMPLETED by the system)",
                final_status in ("DELIVERED", "COMPLETED"),
                f"status {status}, order status {final_status}",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Order ends DELIVERED (or COMPLETED by the system)", str(exc))

        # -- 16. Ledger: balances and matches contract section 6 --------------
        try:
            status, body = await api.call(
                "GET", f"/api/v1/orders/{order_id}/ledger", token=admin_token
            )
            entries = as_items(body)
            debits = 0
            credits = 0
            by_type = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                etype = entry.get("entry_type") or entry.get("type")
                amount = entry.get("amount_cents")
                if amount is None:
                    amount = entry.get("amount")
                if not isinstance(amount, int):
                    continue
                by_type.setdefault(etype, []).append((entry.get("direction"), amount))
                if entry.get("direction") == "debit":
                    debits += amount
                elif entry.get("direction") == "credit":
                    credits += amount
            present_types = set(by_type.keys())
            rec.check(
                "Ledger balances: total debits equal total credits",
                status == 200 and len(entries) > 0 and debits == credits,
                f"status {status}, {len(entries)} entries, "
                f"debits {debits}, credits {credits}",
            )
            missing_types = sorted(LEDGER_ENTRY_TYPES - present_types)
            rec.check(
                "Ledger contains every contract section 6 entry type",
                not missing_types,
                f"types present: {sorted(present_types)}; "
                f"missing: {missing_types if missing_types else 'none'}",
            )
            # Exact amounts per contract section 6 (seeded defaults).
            fee = EXPECTED_DELIVERY_FEE_CENTS
            tax = want_tax
            tip = TIP_CENTS
            pay = DRIVER_BASE_PAY_CENTS
            ff = FULFILLMENT_FEE_CENTS
            want_amounts = {
                ("customer_charge", "debit"): subtotal + fee + tax + tip,
                ("delivery_cost_expense", "debit"): pay,
                ("restaurant_payable", "credit"): subtotal + tax - ff,
                ("delivery_fee_revenue", "credit"): fee,
                ("platform_fee_revenue", "credit"): ff,
                ("driver_payable", "credit"): pay + tip,
            }
            amount_problems = []
            for (etype, direction), want in want_amounts.items():
                got = sum(
                    amt
                    for d, amt in by_type.get(etype, [])
                    if d == direction
                )
                # Tax tolerance of 1 cent flows into the two tax-bearing lines.
                tolerance = 1 if etype in ("customer_charge", "restaurant_payable") else 0
                if abs(got - want) > tolerance:
                    amount_problems.append(f"{etype}/{direction}: got {got}, want {want}")
            rec.check(
                "Ledger amounts match the contract section 6 formulas",
                not amount_problems,
                "all amounts match"
                if not amount_problems
                else "; ".join(amount_problems)
                + " (driver pay and fulfillment fee are seeded defaults: "
                f"{pay} and {ff} cents)",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Ledger balances: total debits equal total credits", str(exc))
            rec.fail("Ledger contains every contract section 6 entry type", str(exc))
            rec.fail("Ledger amounts match the contract section 6 formulas", str(exc))

        # -- 17. Snapshot immutability ----------------------------------------
        # Contract sections 3-4: staff may only change availability, so the
        # price change itself is done as the owner (see ambiguity A6).
        price_item = chosen[0]
        item_id = price_item["id"]
        old_price = money(price_item, "price")
        new_price = (old_price or 0) + 100
        try:
            status, body = await api.call(
                "PATCH",
                f"/api/v1/restaurants/{demo_id}/menu/items/{item_id}",
                token=staff_token,
                json={"price_cents": new_price},
            )
            rec.check(
                "Restaurant staff cannot change a menu price (403 expected)",
                status in (403, 401),
                f"status {status}"
                + ("" if status in (403, 401) else f", body {str(body)[:200]}"),
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Restaurant staff cannot change a menu price", str(exc))

        price_changed = False
        price_field_used = None
        try:
            for field in ("price_cents", "price"):  # see ambiguity A2
                status, body = await api.call(
                    "PATCH",
                    f"/api/v1/restaurants/{demo_id}/menu/items/{item_id}",
                    token=owner_token,
                    json={field: new_price},
                )
                if status in (200, 201):
                    price_changed = True
                    price_field_used = field
                    break
            rec.check(
                "Owner changes the menu item price after the order",
                price_changed,
                f"item {item_id}, price {old_price} -> {new_price} cents"
                + (f" (field {price_field_used})" if price_changed else f", last status {status}"),
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Owner changes the menu item price after the order", str(exc))

        if price_changed:
            try:
                status, body = await api.call(
                    "GET", f"/api/v1/orders/{order_id}", token=customer_token
                )
                totals_after = {
                    "subtotal": money(body, "subtotal"),
                    "delivery_fee": money(body, "delivery_fee"),
                    "tax": money(body, "tax"),
                    "tip": money(body, "tip"),
                    "total": money(body, "total"),
                }
                snapshot_after = body.get("checkout_snapshot") if isinstance(body, dict) else None
                totals_same = totals_after == state["totals_before"]
                snapshot_same = snapshot_after == state["snapshot_before"]
                rec.check(
                    "Checkout snapshot and totals are unchanged after the price change",
                    totals_same and snapshot_same,
                    f"totals same: {totals_same}, snapshot same: {snapshot_same}",
                )
            except Exception as exc:  # noqa: BLE001
                rec.fail(
                    "Checkout snapshot and totals are unchanged after the price change",
                    str(exc),
                )
            # Restore the original price so later runs see the seeded menu.
            try:
                status, _ = await api.call(
                    "PATCH",
                    f"/api/v1/restaurants/{demo_id}/menu/items/{item_id}",
                    token=owner_token,
                    json={price_field_used or "price_cents": old_price},
                )
                if status not in (200, 201):
                    print(
                        f"    NOTE: could not restore the price of menu item "
                        f"{item_id} (status {status}); it is now {new_price} "
                        f"cents instead of {old_price}. Please fix it manually."
                    )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"    NOTE: could not restore the price of menu item "
                    f"{item_id} ({exc}); it is now {new_price} cents instead "
                    f"of {old_price}. Please fix it manually."
                )
        else:
            rec.skip(
                "Checkout snapshot and totals are unchanged after the price change",
                "the price change itself failed",
            )

        # -- 18. Pickup loop ----------------------------------------------------
        pickup_order = None
        try:
            status, body = await api.call(
                "POST",
                "/api/v1/orders",
                token=customer_token,
                json={
                    "restaurant_id": demo_id,
                    "items": [{"menu_item_id": chosen[0]["id"], "quantity": 1}],
                    "fulfillment_type": "pickup",
                    "tip_cents": 0,
                    "channel": "app",
                },
                headers={"Idempotency-Key": f"smoke-{run_id}-pickup"},
            )
            ok = status in (200, 201) and isinstance(body, dict) and body.get("id")
            pickup_order = body if ok else None
            fee = money(body, "delivery_fee") if isinstance(body, dict) else None
            rec.check(
                "Pickup order has no delivery fee",
                ok and fee == 0,
                f"status {status}, delivery fee {fee}"
                + (f", order id {body.get('id')}" if ok else f", body {body}"),
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Pickup order has no delivery fee", f"request failed: {exc}")

        if pickup_order is not None:
            pickup_id = pickup_order["id"]
            await transition(
                "Pickup order: restaurant accepts",
                "POST",
                f"/api/v1/orders/{pickup_id}/accept",
                staff_token,
                {"prep_minutes": PREP_MINUTES},
            )
            await transition(
                "Pickup order: restaurant marks ready",
                "POST",
                f"/api/v1/orders/{pickup_id}/ready",
                staff_token,
            )
            ok_complete, _ = await transition(
                "Pickup order: restaurant completes it (no driver)",
                "POST",
                f"/api/v1/orders/{pickup_id}/complete",
                staff_token,
            )
            # No driver assignment: the pickup order must never appear in the
            # driver's offers, and its status trail must never hit ASSIGNED.
            no_driver = True
            detail_parts = []
            try:
                status, body = await api.call(
                    "GET", "/api/v1/drivers/me/offers", token=driver_token
                )
                offers = as_items(body)
                if any(
                    isinstance(o, dict) and o.get("order_id") == pickup_id
                    for o in offers
                ):
                    no_driver = False
                    detail_parts.append("pickup order appeared in driver offers")
                else:
                    detail_parts.append("not in driver offers")
            except Exception as exc:  # noqa: BLE001
                detail_parts.append(f"offers check failed: {exc}")
            try:
                status, body = await api.call(
                    "GET",
                    f"/api/v1/orders/{pickup_id}/events",
                    token=customer_token,
                )
                events = as_items(body)
                trail = [
                    e.get("to_status")
                    for e in events
                    if isinstance(e, dict)
                ]
                if "ASSIGNED" in trail:
                    no_driver = False
                    detail_parts.append("status trail contains ASSIGNED")
                else:
                    detail_parts.append(f"status trail: {trail}")
            except Exception as exc:  # noqa: BLE001
                detail_parts.append(f"events check failed: {exc}")
            rec.check(
                "Pickup order has no driver assignment",
                no_driver and ok_complete,
                "; ".join(detail_parts),
            )
        else:
            rec.skip("Pickup order: restaurant accepts", "no pickup order placed")
            rec.skip("Pickup order: restaurant marks ready", "no pickup order placed")
            rec.skip(
                "Pickup order: restaurant completes it (no driver)",
                "no pickup order placed",
            )
            rec.skip("Pickup order has no driver assignment", "no pickup order placed")

        # -- 19. RBAC spot checks ----------------------------------------------
        if customer_b_token is not None:
            try:
                status, body = await api.call(
                    "GET", f"/api/v1/orders/{order_id}", token=customer_b_token
                )
                rec.check(
                    "Another customer cannot read the order (403/404 expected)",
                    status in (403, 404),
                    f"status {status}"
                    + ("" if status in (403, 404) else f", body {str(body)[:200]}"),
                )
            except Exception as exc:  # noqa: BLE001
                rec.fail("Another customer cannot read the order", str(exc))
        else:
            rec.skip(
                "Another customer cannot read the order (403/404 expected)",
                "second customer login failed",
            )

        try:
            status_me, _ = await api.call("GET", "/api/v1/users/me")
            status_order, _ = await api.call("GET", f"/api/v1/orders/{order_id}")
            rec.check(
                "Unauthenticated requests are rejected (401 expected)",
                status_me == 401 and status_order == 401,
                f"GET /users/me -> {status_me}, GET /orders/{{id}} -> {status_order}",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Unauthenticated requests are rejected (401 expected)", str(exc))

        # -- 20. Census / prospect check ----------------------------------------
        prospect_count = None
        prospect_ids: set = set()
        prospect_names: set = set()
        try:
            status, body = await api.call(
                "GET",
                "/api/v1/admin/restaurants?status=prospect",
                token=admin_token,
            )
            prospects = as_items(body)
            prospect_count = len(prospects)
            for p in prospects:
                if isinstance(p, dict):
                    if p.get("id") is not None:
                        prospect_ids.add(p["id"])
                    if p.get("name"):
                        prospect_names.add(str(p["name"]).lower())
            # Informational only: zero is fine if the census has not been
            # imported yet. Never fails on zero.
            rec.ok(
                "Admin prospect list reports a count (zero is fine pre-import)",
                f"status {status}, {prospect_count} prospect restaurants",
            )
        except Exception as exc:  # noqa: BLE001
            rec.fail("Admin prospect list reports a count", f"request failed: {exc}")

        if prospect_count is not None:
            leaked = [
                r
                for r in public_restaurants
                if isinstance(r, dict)
                and (
                    r.get("id") in prospect_ids
                    or str(r.get("name", "")).lower() in prospect_names
                )
            ]
            rec.check(
                "Public restaurant list contains zero prospects",
                not leaked,
                f"{len(public_restaurants)} public restaurants, "
                f"{prospect_count} prospects in admin, "
                f"{len(leaked)} leaked"
                + (
                    ""
                    if prospect_count
                    else " (no prospects exist yet, so the cross-check is vacuous)"
                ),
            )
        else:
            rec.skip(
                "Public restaurant list contains zero prospects",
                "admin prospect list could not be read",
            )

    return 0 if rec.summary() else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
