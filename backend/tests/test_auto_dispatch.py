"""Automatic dispatch: a READY delivery order is offered to the best
available driver at once (approved, online, no active task, has not
declined that order), fairest first. When no driver is free the order
waits, and the queue runs again when a driver comes online, declines,
or finishes a delivery."""

from tests.conftest import auth_headers, demo_headers, login, place_standard_order


def _available_item(seeded):
    return next(i for i in seeded["items"] if i["available"])


def _ready_order(client, seeded, customer, staff):
    item = _available_item(seeded)
    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    order_id = order["id"]
    client.post(
        f"/api/v1/orders/{order_id}/accept",
        json={"prep_minutes": 5},
        headers=staff,
    )
    resp = client.post(f"/api/v1/orders/{order_id}/ready", headers=staff)
    assert resp.status_code == 200, resp.text
    return order_id, resp.json()["status"]


def _go_online(client, headers):
    resp = client.patch(
        "/api/v1/drivers/me/availability", json={"online": True}, headers=headers
    )
    assert resp.status_code == 200, resp.text


def _offers(client, headers):
    return client.get("/api/v1/drivers/me/offers", headers=headers).json()["items"]


def _second_driver(client, admin):
    """Register + approve a second driver; returns (headers, driver_id)."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "driver2@example.com",
            "password": "Password123!",
            "full_name": "Driver Two",
            "role": "driver",
        },
    )
    assert resp.status_code == 201, resp.text
    headers = auth_headers(resp.json()["access_token"])
    me = client.get("/api/v1/drivers/me", headers=headers).json()
    resp = client.post(
        f"/api/v1/admin/drivers/{me['id']}/approve", headers=admin
    )
    assert resp.status_code == 200, resp.text
    return headers, me["id"]


def test_ready_order_auto_assigns_to_online_driver(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    driver = demo_headers(client, "driver")
    _go_online(client, driver)

    order_id, status = _ready_order(client, seeded, customer, staff)
    # The ready response itself already shows the assignment.
    assert status == "ASSIGNED"
    offers = _offers(client, driver)
    assert len(offers) == 1
    assert offers[0]["order_id"] == order_id
    assert offers[0]["status"] == "offered"

    # The transition is audited as automatic.
    events = client.get(f"/api/v1/orders/{order_id}/events", headers=customer).json()
    auto = [e for e in events["items"] if e["to_status"] == "ASSIGNED"]
    assert len(auto) == 1
    assert auto[0]["reason"] == "Auto-assigned"


def test_ready_order_waits_then_assigns_when_driver_comes_online(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    driver = demo_headers(client, "driver")

    order_id, status = _ready_order(client, seeded, customer, staff)
    assert status == "READY"
    assert _offers(client, driver) == []

    _go_online(client, driver)
    order = client.get(f"/api/v1/orders/{order_id}", headers=customer).json()
    assert order["status"] == "ASSIGNED"
    offers = _offers(client, driver)
    assert len(offers) == 1
    assert offers[0]["order_id"] == order_id


def test_decline_reassigns_to_next_driver(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    driver1 = demo_headers(client, "driver")
    admin = demo_headers(client, "admin")
    driver2, _ = _second_driver(client, admin)
    _go_online(client, driver1)
    _go_online(client, driver2)

    order_id, status = _ready_order(client, seeded, customer, staff)
    assert status == "ASSIGNED"
    # Both drivers never tasked: the lowest driver id (the seeded one) first.
    offers1 = _offers(client, driver1)
    assert len(offers1) == 1
    assert _offers(client, driver2) == []

    resp = client.post(
        f"/api/v1/drivers/me/offers/{offers1[0]['id']}/decline", headers=driver1
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "declined"
    # The decliner is excluded, so the next driver is offered at once.
    assert _offers(client, driver1) == []
    offers2 = _offers(client, driver2)
    assert len(offers2) == 1
    assert offers2[0]["order_id"] == order_id
    order = client.get(f"/api/v1/orders/{order_id}", headers=customer).json()
    assert order["status"] == "ASSIGNED"


def test_busy_driver_is_skipped(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    driver1 = demo_headers(client, "driver")
    admin = demo_headers(client, "admin")
    driver2, _ = _second_driver(client, admin)
    _go_online(client, driver1)
    _go_online(client, driver2)

    # First order goes to driver1, who accepts (now busy).
    order1, _ = _ready_order(client, seeded, customer, staff)
    offers1 = _offers(client, driver1)
    assert len(offers1) == 1
    resp = client.post(
        f"/api/v1/drivers/me/offers/{offers1[0]['id']}/accept", headers=driver1
    )
    assert resp.status_code == 200, resp.text

    # Second order skips the busy driver1 and goes to driver2.
    order2, status = _ready_order(client, seeded, customer, staff)
    assert status == "ASSIGNED"
    assert _offers(client, driver1) == []
    offers2 = _offers(client, driver2)
    assert len(offers2) == 1
    assert offers2[0]["order_id"] == order2


def test_fairness_never_tasked_driver_first(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    driver1 = demo_headers(client, "driver")
    admin = demo_headers(client, "admin")
    driver2, _ = _second_driver(client, admin)
    _go_online(client, driver1)
    _go_online(client, driver2)

    # Driver1 takes and completes the first delivery.
    _ready_order(client, seeded, customer, staff)
    task = _offers(client, driver1)[0]
    client.post(
        f"/api/v1/drivers/me/offers/{task['id']}/accept", headers=driver1
    )
    client.post(f"/api/v1/deliveries/{task['id']}/pickup", headers=driver1)
    resp = client.post(
        f"/api/v1/deliveries/{task['id']}/deliver",
        json={"proof_note": "Left at the door"},
        headers=driver1,
    )
    assert resp.status_code == 200, resp.text

    # Next order goes to driver2, who never had a task — not to driver1,
    # who just finished one.
    order2, status = _ready_order(client, seeded, customer, staff)
    assert status == "ASSIGNED"
    assert _offers(client, driver1) == []
    offers2 = _offers(client, driver2)
    assert len(offers2) == 1
    assert offers2[0]["order_id"] == order2


def test_pickup_order_never_auto_assigned(client, seeded):
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    driver = demo_headers(client, "driver")
    _go_online(client, driver)

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
        f"/api/v1/orders/{order['id']}/accept",
        json={"prep_minutes": 5},
        headers=staff,
    )
    resp = client.post(f"/api/v1/orders/{order['id']}/ready", headers=staff)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "READY"
    assert _offers(client, driver) == []
