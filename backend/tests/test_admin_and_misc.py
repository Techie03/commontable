"""Admin, menu management, cancel/reject, and notification tests."""

from tests.conftest import demo_headers, place_standard_order


def _available_item(seeded):
    return next(i for i in seeded["items"] if i["available"])


def test_menu_item_crud_and_staff_availability_only(client, seeded):
    owner = demo_headers(client, "owner")
    staff = demo_headers(client, "staff")
    restaurant_id = seeded["restaurant_id"]

    created = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/items",
        json={
            "name": "Demo Soup",
            "description": "Demo item",
            "price_cents": 599,
            "category": "Mains",
        },
        headers=owner,
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]

    # Staff may toggle availability but may not change the price.
    resp = client.patch(
        f"/api/v1/restaurants/{restaurant_id}/menu/items/{item_id}",
        json={"available": False},
        headers=staff,
    )
    assert resp.status_code == 200
    assert resp.json()["available"] is False
    resp = client.patch(
        f"/api/v1/restaurants/{restaurant_id}/menu/items/{item_id}",
        json={"price_cents": 1},
        headers=staff,
    )
    assert resp.status_code == 403

    # Owner can delete an item that is on no order.
    resp = client.delete(
        f"/api/v1/restaurants/{restaurant_id}/menu/items/{item_id}",
        headers=owner,
    )
    assert resp.status_code == 200


def test_menu_item_on_order_cannot_be_deleted(client, seeded):
    customer = demo_headers(client, "customer")
    owner = demo_headers(client, "owner")
    item = _available_item(seeded)
    place_standard_order(client, customer, seeded["restaurant_id"], item["id"])
    resp = client.delete(
        f"/api/v1/restaurants/{seeded['restaurant_id']}/menu/items/{item['id']}",
        headers=owner,
    )
    assert resp.status_code == 409


def test_cancel_and_reject_flows(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    item = _available_item(seeded)

    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    resp = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "Changed my mind"},
        headers=customer,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "CANCELLED"
    # A cancelled order cannot be accepted.
    assert (
        client.post(
            f"/api/v1/orders/{order['id']}/accept",
            json={"prep_minutes": 5},
            headers=staff,
        ).status_code
        == 400
    )

    order2 = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    resp = client.post(
        f"/api/v1/orders/{order2['id']}/reject",
        json={"reason": "Kitchen is closed"},
        headers=staff,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "REJECTED"


def test_admin_zones_pricing_metrics(client, seeded):
    admin = demo_headers(client, "admin")
    zones = client.get("/api/v1/admin/zones", headers=admin).json()
    assert zones["total"] == 1
    assert zones["items"][0]["name"] == "Denton"
    assert zones["items"][0]["tax_rate_bps"] == 825
    assert zones["items"][0]["boundary_geojson"]["type"] == "Polygon"

    pricing = client.get("/api/v1/admin/pricing", headers=admin).json()
    keys = {r["rule_key"] for r in pricing["items"]}
    assert keys == {
        "standard_delivery_fee_cents",
        "pickup_delivery_fee_cents",
        "driver_base_pay_cents",
        "restaurant_fulfillment_fee_cents",
    }
    fee_rule = next(
        r for r in pricing["items"] if r["rule_key"] == "standard_delivery_fee_cents"
    )
    assert fee_rule["value_cents"] == 399

    metrics = client.get("/api/v1/admin/metrics", headers=admin).json()
    assert metrics["total_orders"] == 0
    assert metrics["orders_by_status"] == {}
    assert metrics["revenue_fees_today_cents"] == 0

    # Restaurant reports work for the owner.
    owner = demo_headers(client, "owner")
    reports = client.get(
        f"/api/v1/restaurants/{seeded['restaurant_id']}/reports", headers=owner
    ).json()
    assert reports["order_count"] == 0


def test_notifications_read_flow(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    item = _available_item(seeded)
    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/accept", json={"prep_minutes": 5}, headers=staff
    )
    notifs = client.get("/api/v1/notifications", headers=customer).json()
    assert notifs["total"] == 2
    assert notifs["unread_count"] == 2
    first_id = notifs["items"][0]["id"]
    resp = client.post(f"/api/v1/notifications/{first_id}/read", headers=customer)
    assert resp.status_code == 200
    assert resp.json()["read"] is True
    resp = client.post("/api/v1/notifications/read-all", headers=customer)
    assert resp.status_code == 200
    assert resp.json()["marked_read"] == 1


def test_restaurant_staff_gets_placed_notification(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    item = _available_item(seeded)
    place_standard_order(client, customer, seeded["restaurant_id"], item["id"])
    notifs = client.get("/api/v1/notifications", headers=staff).json()
    assert any(n["type"] == "order_placed" for n in notifs["items"])


def test_dispatch_override_withdraws_and_reoffers(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    dispatch = demo_headers(client, "dispatch")
    admin = demo_headers(client, "admin")
    item = _available_item(seeded)

    # Second approved driver.
    client.post(
        "/api/v1/auth/register",
        json={"email": "driver2@example.com", "password": "Password123!", "full_name": "Driver Two"},
    )
    users = client.get("/api/v1/admin/users", headers=admin).json()
    driver2_user = next(u for u in users["items"] if u["email"] == "driver2@example.com")
    client.patch(
        f"/api/v1/admin/users/{driver2_user['id']}/roles",
        json={"add": ["driver"]},
        headers=admin,
    )
    # Approve the new driver via the admin endpoint (find driver id from board
    # after going online is not possible pre-approval; use the users list
    # plus a direct lookup through the dispatch board after approval).
    from app.db.session import SessionLocal
    from app.models.drivers import Driver

    db = SessionLocal()
    driver2 = db.query(Driver).filter(Driver.user_id == driver2_user["id"]).first()
    driver2_id = driver2.id
    db.close()
    client.post(f"/api/v1/admin/drivers/{driver2_id}/approve", headers=admin)

    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/accept", json={"prep_minutes": 5}, headers=staff
    )
    client.post(f"/api/v1/orders/{order['id']}/ready", headers=staff)
    task = client.post(
        "/api/v1/dispatch/assign",
        json={"order_id": order["id"], "driver_id": seeded["driver_id"]},
        headers=dispatch,
    ).json()
    resp = client.post(
        "/api/v1/dispatch/override",
        json={
            "order_id": order["id"],
            "driver_id": driver2_id,
            "reason": "First driver is too far",
        },
        headers=dispatch,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["driver_id"] == driver2_id
    assert resp.json()["id"] != task["id"]
    order = client.get(f"/api/v1/orders/{order['id']}", headers=customer).json()
    assert order["status"] == "ASSIGNED"
