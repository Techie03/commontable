"""Full order-loop test: Standard delivery end to end.

register -> place -> accept -> ready -> assign -> driver accept -> pickup
-> deliver -> ledger balances -> checkout snapshot immutable after a menu
price change. Also asserts the two-transition accept and deliver events.
"""

from tests.conftest import demo_headers, place_standard_order


def _available_item(seeded):
    return next(i for i in seeded["items"] if i["available"])


def test_full_standard_order_loop(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    dispatch = demo_headers(client, "dispatch")
    driver = demo_headers(client, "driver")
    admin = demo_headers(client, "admin")
    restaurant_id = seeded["restaurant_id"]
    item = _available_item(seeded)

    # Serviceability is public; the demo restaurant's menu is visible to
    # its own staff (anonymous customers never see demo restaurants).
    svc = client.get("/api/v1/dispatch/serviceability?postal_code=76201")
    assert svc.status_code == 200
    assert svc.json()["serviceable"] is True
    assert svc.json()["fulfillment_options"] == ["pickup", "standard"]
    menu = client.get(
        f"/api/v1/restaurants/{restaurant_id}/menu", headers=staff
    )
    assert menu.status_code == 200
    assert "items" in menu.json()
    assert len(menu.json()["items"]) == 6

    # Place the order (201). Subtotal 1080, fee 399, tax 89 (8.25% of 1080
    # rounds to 89), tip 100, total 1668.
    resp = place_standard_order(client, customer, restaurant_id, item["id"])
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["status"] == "PLACED"
    assert order["subtotal_cents"] == 1080
    assert order["delivery_fee_cents"] == 399
    assert order["tax_cents"] == 89
    assert order["tip_cents"] == 100
    assert order["total_cents"] == 1668
    assert order["checkout_snapshot"]["total_cents"] == 1668
    order_id = order["id"]

    # Restaurant accepts: two transitions (PLACED->ACCEPTED->PREPARING).
    resp = client.post(
        f"/api/v1/orders/{order_id}/accept",
        json={"prep_minutes": 20},
        headers=staff,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PREPARING"
    assert resp.json()["prep_minutes"] == 20

    events = client.get(f"/api/v1/orders/{order_id}/events", headers=customer).json()
    transitions = [(e["from_status"], e["to_status"]) for e in events["items"]]
    assert (None, "PLACED") in transitions
    assert ("PLACED", "ACCEPTED") in transitions
    assert ("ACCEPTED", "PREPARING") in transitions

    # Ready.
    resp = client.post(f"/api/v1/orders/{order_id}/ready", headers=staff)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "READY"

    # Dispatch board shows the ready order and the online driver with ids.
    client.patch("/api/v1/drivers/me/availability", json={"online": True}, headers=driver)
    board = client.get("/api/v1/dispatch/board", headers=dispatch)
    assert board.status_code == 200
    assert any(o["id"] == order_id for o in board.json()["ready_orders"])
    assert any(
        d["driver_id"] == seeded["driver_id"] for d in board.json()["online_drivers"]
    )

    # Assign, driver accepts, pickup, deliver.
    resp = client.post(
        "/api/v1/dispatch/assign",
        json={"order_id": order_id, "driver_id": seeded["driver_id"]},
        headers=dispatch,
    )
    assert resp.status_code == 200, resp.text
    task = resp.json()
    assert task["status"] == "offered"
    assert task["pay_cents"] == 350  # 250 base pay + 100 tip
    task_id = task["id"]

    offers = client.get("/api/v1/drivers/me/offers", headers=driver).json()
    assert any(o["id"] == task_id and o["pay_cents"] == 350 for o in offers["items"])

    resp = client.post(
        f"/api/v1/drivers/me/offers/{task_id}/accept", headers=driver
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "accepted"

    resp = client.post(f"/api/v1/deliveries/{task_id}/pickup", headers=driver)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "picked_up"

    resp = client.post(
        f"/api/v1/deliveries/{task_id}/deliver",
        json={"proof_note": "Left at the door"},
        headers=driver,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "delivered"

    order = client.get(f"/api/v1/orders/{order_id}", headers=customer).json()
    assert order["status"] == "COMPLETED"

    # Deliver wrote two transitions (PICKED_UP->DELIVERED->COMPLETED).
    events = client.get(f"/api/v1/orders/{order_id}/events", headers=customer).json()
    transitions = [(e["from_status"], e["to_status"]) for e in events["items"]]
    assert ("PICKED_UP", "DELIVERED") in transitions
    assert ("DELIVERED", "COMPLETED") in transitions

    # Ledger balances: debits == credits.
    ledger = client.get(f"/api/v1/orders/{order_id}/ledger", headers=admin).json()
    assert ledger["total"] == 6
    debits = sum(e["amount_cents"] for e in ledger["items"] if e["direction"] == "debit")
    credits = sum(e["amount_cents"] for e in ledger["items"] if e["direction"] == "credit")
    assert debits == credits == 1918  # 1668 customer charge + 250 driver pay
    types = {e["entry_type"] for e in ledger["items"]}
    assert types == {
        "customer_charge",
        "delivery_cost_expense",
        "restaurant_payable",
        "delivery_fee_revenue",
        "platform_fee_revenue",
        "driver_payable",
    }

    # Customer got status notifications.
    notifs = client.get("/api/v1/notifications", headers=customer).json()
    notif_types = {n["type"] for n in notifs["items"]}
    assert {"order_accepted", "order_preparing", "driver_assigned",
            "order_picked_up", "order_delivered"} <= notif_types

    # Driver earnings show the delivery.
    earnings = client.get("/api/v1/drivers/me/earnings", headers=driver).json()
    assert earnings["deliveries"] == 1
    assert earnings["total_pay_cents"] == 350

    # Checkout snapshot is immutable: change the menu price, the order and
    # its snapshot do not move.
    client.patch(
        f"/api/v1/restaurants/{restaurant_id}/menu/items/{item['id']}",
        json={"price_cents": 9999},
        headers=demo_headers(client, "owner"),
    )
    order_after = client.get(f"/api/v1/orders/{order_id}", headers=customer).json()
    assert order_after["total_cents"] == 1668
    assert order_after["checkout_snapshot"]["total_cents"] == 1668
    assert order_after["checkout_snapshot"]["items"][0]["price_cents"] == 1080
    assert order_after["items"][0]["price_snapshot_cents"] == 1080

    # Rating after delivery.
    resp = client.post(
        f"/api/v1/orders/{order_id}/ratings",
        json={"score": 5, "comment": "Great demo meal"},
        headers=customer,
    )
    assert resp.status_code == 201, resp.text


def test_fulfillment_saver_and_express_rejected(client, seeded):
    customer = demo_headers(client, "customer")
    item = _available_item(seeded)
    for fulfillment in ("saver", "express"):
        resp = place_standard_order(
            client, customer, seeded["restaurant_id"], item["id"],
            fulfillment_type=fulfillment,
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["code"] == "fulfillment_not_supported"


def test_unavailable_item_cannot_be_ordered(client, seeded):
    customer = demo_headers(client, "customer")
    unavailable = next(i for i in seeded["items"] if not i["available"])
    resp = place_standard_order(
        client, customer, seeded["restaurant_id"], unavailable["id"]
    )
    assert resp.status_code == 400


def test_not_serviceable_postal_code(client, seeded):
    customer = demo_headers(client, "customer")
    item = _available_item(seeded)
    resp = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"],
        delivery_address={
            "line1": "1 Far Away Rd",
            "city": "Dallas",
            "state": "TX",
            "postal_code": "75201",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "not_serviceable"
