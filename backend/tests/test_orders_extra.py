"""Pickup loop, Direct2Door orders, decline/reassign, refunds, RBAC."""

from tests.conftest import (
    DEMO_EMAILS,
    demo_headers,
    login,
    place_standard_order,
)


def _available_item(seeded):
    return next(i for i in seeded["items"] if i["available"])


def test_pickup_order_loop(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    admin = demo_headers(client, "admin")
    restaurant_id = seeded["restaurant_id"]
    item = _available_item(seeded)

    resp = client.post(
        "/api/v1/orders",
        json={
            "restaurant_id": restaurant_id,
            "items": [{"menu_item_id": item["id"], "quantity": 2}],
            "fulfillment_type": "pickup",
            "tip_cents": 0,
            "channel": "app",
        },
        headers=customer,
    )
    assert resp.status_code == 201, resp.text
    order = resp.json()
    # Subtotal 2160, no delivery fee, tax 178 (8.25% of 2160 = 178.2), total 2338.
    assert order["delivery_fee_cents"] == 0
    assert order["subtotal_cents"] == 2160
    assert order["tax_cents"] == 178
    assert order["total_cents"] == 2338
    order_id = order["id"]

    assert client.post(
        f"/api/v1/orders/{order_id}/accept", json={"prep_minutes": 10}, headers=staff
    ).status_code == 200
    assert client.post(f"/api/v1/orders/{order_id}/ready", headers=staff).status_code == 200
    resp = client.post(f"/api/v1/orders/{order_id}/complete", headers=staff)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COMPLETED"

    # Pickup ledger: two entries, balanced.
    ledger = client.get(f"/api/v1/orders/{order_id}/ledger", headers=admin).json()
    assert ledger["total"] == 2
    debits = sum(e["amount_cents"] for e in ledger["items"] if e["direction"] == "debit")
    credits = sum(e["amount_cents"] for e in ledger["items"] if e["direction"] == "credit")
    assert debits == credits == 2338


def test_pickup_order_cannot_be_assigned(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    dispatch = demo_headers(client, "dispatch")
    item = _available_item(seeded)
    order = client.post(
        "/api/v1/orders",
        json={
            "restaurant_id": seeded["restaurant_id"],
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "fulfillment_type": "pickup",
        },
        headers=customer,
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/accept", json={"prep_minutes": 5}, headers=staff
    )
    client.post(f"/api/v1/orders/{order['id']}/ready", headers=staff)
    # Pickup orders never go through dispatch; complete is the restaurant path.
    resp = client.post(
        "/api/v1/dispatch/assign",
        json={"order_id": order["id"], "driver_id": seeded["driver_id"]},
        headers=dispatch,
    )
    # Assigning a pickup order is a misuse of the endpoint; the slice allows
    # the call only for delivery orders, so it must fail.
    assert resp.status_code in (400, 422), resp.text


def test_direct2door_order_by_restaurant_staff(client, seeded):
    staff = demo_headers(client, "staff")
    customer = demo_headers(client, "customer")
    item = _available_item(seeded)
    resp = client.post(
        "/api/v1/orders",
        json={
            "restaurant_id": seeded["restaurant_id"],
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "fulfillment_type": "standard",
            "delivery_address": {
                "line1": "456 Oak St",
                "city": "Denton",
                "state": "TX",
                "postal_code": "76205",
            },
            "channel": "direct2door",
            "customer_name": "Walk In Guest",
            "customer_phone": "(940) 555-0123",
        },
        headers=staff,
    )
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["channel"] == "direct2door"
    assert order["customer_name"] == "Walk In Guest"
    assert order["customer_id"] is None
    # It appears in the same restaurant queue.
    queue = client.get(
        f"/api/v1/restaurants/{seeded['restaurant_id']}/orders", headers=staff
    ).json()
    assert any(o["id"] == order["id"] for o in queue["items"])
    # A customer cannot place a Direct2Door order.
    resp = client.post(
        "/api/v1/orders",
        json={
            "restaurant_id": seeded["restaurant_id"],
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "fulfillment_type": "standard",
            "delivery_address": {
                "line1": "456 Oak St",
                "city": "Denton",
                "state": "TX",
                "postal_code": "76205",
            },
            "channel": "direct2door",
            "customer_name": "X",
            "customer_phone": "1",
        },
        headers=customer,
    )
    assert resp.status_code == 403


def test_driver_decline_reverts_to_ready(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    dispatch = demo_headers(client, "dispatch")
    driver = demo_headers(client, "driver")
    item = _available_item(seeded)
    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    order_id = order["id"]
    client.post(f"/api/v1/orders/{order_id}/accept", json={"prep_minutes": 5}, headers=staff)
    client.post(f"/api/v1/orders/{order_id}/ready", headers=staff)
    task = client.post(
        "/api/v1/dispatch/assign",
        json={"order_id": order_id, "driver_id": seeded["driver_id"]},
        headers=dispatch,
    ).json()
    resp = client.post(
        f"/api/v1/drivers/me/offers/{task['id']}/decline", headers=driver
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "declined"
    order = client.get(f"/api/v1/orders/{order_id}", headers=customer).json()
    assert order["status"] == "READY"
    # Dispatcher can reassign.
    resp = client.post(
        "/api/v1/dispatch/assign",
        json={"order_id": order_id, "driver_id": seeded["driver_id"]},
        headers=dispatch,
    )
    assert resp.status_code == 200, resp.text


def test_full_refund_reverses_ledger_and_refunds_order(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    admin = demo_headers(client, "admin")
    item = _available_item(seeded)
    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    order_id = order["id"]
    resp = client.post(
        f"/api/v1/orders/{order_id}/refunds",
        json={"reason": "Customer asked for a refund"},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["amount_cents"] == order["total_cents"]
    order = client.get(f"/api/v1/orders/{order_id}", headers=customer).json()
    assert order["status"] == "REFUNDED"
    ledger = client.get(f"/api/v1/orders/{order_id}/ledger", headers=admin).json()
    assert ledger["total"] == 12  # 6 original + 6 reversing entries
    debits = sum(e["amount_cents"] for e in ledger["items"] if e["direction"] == "debit")
    credits = sum(e["amount_cents"] for e in ledger["items"] if e["direction"] == "credit")
    assert debits == credits


def test_payment_intent_is_stub_no_charge(client, seeded):
    customer = demo_headers(client, "customer")
    item = _available_item(seeded)
    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    resp = client.post(
        "/api/v1/payments/intent", json={"order_id": order["id"]}, headers=customer
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["provider"] == "stub"
    assert body["status"] == "stub_no_charge"
    assert "No real payment is processed" in body["message"]


def test_rbac_customer_cannot_read_another_customers_order(client, seeded):
    customer = demo_headers(client, "customer")
    item = _available_item(seeded)
    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    # Register a second customer and try to read the first customer's order.
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "Password123!", "full_name": "Other"},
    )
    other = login(client, "other@example.com", password="Password123!")
    headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"/api/v1/orders/{order['id']}", headers=headers).status_code == 403
    # The other customer also does not see it in their list.
    mine = client.get("/api/v1/orders", headers=headers).json()
    assert all(o["id"] != order["id"] for o in mine["items"])


def test_rbac_staff_cannot_see_another_restaurants_orders(client, seeded):
    admin = demo_headers(client, "admin")
    staff = demo_headers(client, "staff")
    # Admin creates a second restaurant (pending -> verified -> approved)
    # with its own order.
    second = client.post(
        "/api/v1/restaurants",
        json={
            "name": "Second Diner",
            "phone": "(940) 555-0200",
            "owner_name": "Second Owner",
            "business_address": "2 Test St, Denton, TX 76201",
        },
        headers=admin,
    ).json()
    client.post(f"/api/v1/admin/restaurants/{second['id']}/verify", headers=admin)
    client.post(f"/api/v1/admin/restaurants/{second['id']}/approve", headers=admin)
    # Demo Diner staff have no role at the second restaurant.
    assert (
        client.get(f"/api/v1/restaurants/{second['id']}/orders", headers=staff).status_code
        == 403
    )
    # And the second restaurant is not in their order list scope.
    mine = client.get("/api/v1/orders", headers=staff).json()
    assert all(o["restaurant_id"] == seeded["restaurant_id"] for o in mine["items"])


def test_rbac_customer_cannot_use_admin_endpoints(client, seeded):
    customer = demo_headers(client, "customer")
    assert client.get("/api/v1/admin/users", headers=customer).status_code == 403
    assert client.get("/api/v1/admin/metrics", headers=customer).status_code == 403
    assert client.get("/api/v1/dispatch/board", headers=customer).status_code == 403
