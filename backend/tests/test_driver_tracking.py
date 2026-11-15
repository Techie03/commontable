"""Live driver tracking: a driver on an active delivery reports their
position, the latest ping is stored, and the order's channel gets a
driver.location_updated event. No active delivery means no audience, so
the ping is refused. The tracking snapshot gives the order's customer
the driver, their latest position, and the restaurant's coordinates."""

from tests.conftest import demo_headers, demo_token, place_standard_order


def _available_item(seeded):
    return next(i for i in seeded["items"] if i["available"])


def _active_delivery(client, seeded):
    """Ready order, driver online (auto-assigned), offer accepted.
    Returns (order_id, driver headers)."""
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    driver = demo_headers(client, "driver")
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
    resp = client.patch(
        "/api/v1/drivers/me/availability",
        json={"online": True},
        headers=driver,
    )
    assert resp.status_code == 200, resp.text
    offers = client.get("/api/v1/drivers/me/offers", headers=driver).json()[
        "items"
    ]
    assert len(offers) == 1, offers
    resp = client.post(
        f"/api/v1/drivers/me/offers/{offers[0]['id']}/accept",
        headers=driver,
    )
    assert resp.status_code == 200, resp.text
    return order_id, driver


def test_location_update_stores_latest_ping(client, seeded):
    order_id, driver = _active_delivery(client, seeded)
    resp = client.post(
        "/api/v1/drivers/me/location",
        json={"latitude": 33.21, "longitude": -97.13, "heading": 90, "speed": 8.5},
        headers=driver,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["latitude"] == 33.21
    assert body["longitude"] == -97.13
    assert body["heading"] == 90
    assert body["speed"] == 8.5
    assert body["at"] is not None
    # A second ping replaces the first; only the latest is kept.
    resp = client.post(
        "/api/v1/drivers/me/location",
        json={"latitude": 33.22, "longitude": -97.14},
        headers=driver,
    )
    assert resp.status_code == 200, resp.text
    tracking = client.get(
        f"/api/v1/orders/{order_id}/tracking",
        headers=demo_headers(client, "customer"),
    ).json()
    assert tracking["driver_location"]["latitude"] == 33.22
    assert tracking["driver_location"]["longitude"] == -97.14


def test_location_update_without_active_delivery_is_refused(client, seeded):
    driver = demo_headers(client, "driver")
    resp = client.post(
        "/api/v1/drivers/me/location",
        json={"latitude": 33.21, "longitude": -97.13},
        headers=driver,
    )
    assert resp.status_code == 409, resp.text


def test_location_update_validates_coordinates(client, seeded):
    _, driver = _active_delivery(client, seeded)
    resp = client.post(
        "/api/v1/drivers/me/location",
        json={"latitude": 91, "longitude": -97.13},
        headers=driver,
    )
    assert resp.status_code == 422, resp.text
    resp = client.post(
        "/api/v1/drivers/me/location",
        json={"latitude": 33.21, "longitude": 181},
        headers=driver,
    )
    assert resp.status_code == 422, resp.text


def test_location_update_requires_driver_role(client, seeded):
    resp = client.post(
        "/api/v1/drivers/me/location",
        json={"latitude": 33.21, "longitude": -97.13},
        headers=demo_headers(client, "customer"),
    )
    assert resp.status_code == 403, resp.text


def test_tracking_snapshot_for_customer(client, seeded):
    order_id, driver = _active_delivery(client, seeded)
    client.post(
        "/api/v1/drivers/me/location",
        json={"latitude": 33.21, "longitude": -97.13},
        headers=driver,
    )
    resp = client.get(
        f"/api/v1/orders/{order_id}/tracking",
        headers=demo_headers(client, "customer"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_id"] == order_id
    assert body["driver"] is not None
    assert body["driver"]["name"] == "Demo Driver"
    assert body["driver_location"]["latitude"] == 33.21
    # Demo Diner is seeded at 33.21, -97.13.
    assert body["restaurant"]["latitude"] == 33.21
    assert body["restaurant"]["longitude"] == -97.13


def test_tracking_snapshot_forbids_other_customers(client, seeded):
    order_id, _ = _active_delivery(client, seeded)
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "password": "Password123!",
            "full_name": "Other Customer",
            "role": "customer",
        },
    )
    assert resp.status_code == 201, resp.text
    from tests.conftest import auth_headers

    other = auth_headers(resp.json()["access_token"])
    resp = client.get(f"/api/v1/orders/{order_id}/tracking", headers=other)
    assert resp.status_code == 403, resp.text


def test_location_update_broadcasts_to_order_channel(client, seeded):
    order_id, driver = _active_delivery(client, seeded)
    token = demo_token(client, "customer")
    ws_url = "/api/v1/ws/orders/" + str(order_id) + "?token=" + token
    with client.websocket_connect(ws_url) as ws:
        resp = client.post(
            "/api/v1/drivers/me/location",
            json={"latitude": 33.215, "longitude": -97.135, "heading": 45},
            headers=driver,
        )
        assert resp.status_code == 200, resp.text
        msg = ws.receive_json()
        assert msg["type"] == "driver.location_updated", msg
        assert msg["data"]["order_id"] == order_id
        assert msg["data"]["latitude"] == 33.215
        assert msg["data"]["longitude"] == -97.135
        assert msg["data"]["heading"] == 45
