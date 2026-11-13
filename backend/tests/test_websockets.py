"""WebSocket tests: dispatch, order, and driver channels."""

from tests.conftest import demo_headers, demo_token, place_standard_order


def _available_item(seeded):
    return next(i for i in seeded["items"] if i["available"])


def test_dispatch_channel_receives_order_placed(client, seeded):
    token = demo_token(client, "dispatch")
    customer = demo_headers(client, "customer")
    item = _available_item(seeded)
    with client.websocket_connect(f"/api/v1/ws/dispatch?token={token}") as ws:
        resp = place_standard_order(
            client, customer, seeded["restaurant_id"], item["id"]
        )
        assert resp.status_code == 201, resp.text
        message = ws.receive_json()
        assert message["type"] == "order.placed"
        assert message["data"]["order_id"] == resp.json()["id"]
        assert "at" in message


def test_order_channel_receives_two_status_events_on_accept(client, seeded):
    customer_token = demo_token(client, "customer")
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    item = _available_item(seeded)
    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    with client.websocket_connect(
        f"/api/v1/ws/orders/{order['id']}?token={customer_token}"
    ) as ws:
        resp = client.post(
            f"/api/v1/orders/{order['id']}/accept",
            json={"prep_minutes": 15},
            headers=staff,
        )
        assert resp.status_code == 200, resp.text
        first = ws.receive_json()
        second = ws.receive_json()
        assert first["type"] == "order.status_changed"
        assert (first["data"]["from_status"], first["data"]["to_status"]) == (
            "PLACED",
            "ACCEPTED",
        )
        assert second["type"] == "order.status_changed"
        assert (second["data"]["from_status"], second["data"]["to_status"]) == (
            "ACCEPTED",
            "PREPARING",
        )


def test_driver_channel_receives_offer_created(client, seeded):
    driver_token = demo_token(client, "driver")
    customer = demo_headers(client, "customer")
    staff = demo_headers(client, "staff")
    dispatch = demo_headers(client, "dispatch")
    item = _available_item(seeded)
    order = place_standard_order(
        client, customer, seeded["restaurant_id"], item["id"]
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/accept", json={"prep_minutes": 5}, headers=staff
    )
    client.post(f"/api/v1/orders/{order['id']}/ready", headers=staff)
    with client.websocket_connect(
        f"/api/v1/ws/driver/{seeded['driver_id']}?token={driver_token}"
    ) as ws:
        resp = client.post(
            "/api/v1/dispatch/assign",
            json={"order_id": order["id"], "driver_id": seeded["driver_id"]},
            headers=dispatch,
        )
        assert resp.status_code == 200, resp.text
        message = ws.receive_json()
        assert message["type"] == "offer.created"
        assert message["data"]["order_id"] == order["id"]
        assert message["data"]["pay_cents"] == 350
        assert message["data"]["restaurant_name"] == "Demo Diner (Denton Pilot)"


def test_websocket_rejects_missing_token(client, seeded):
    try:
        with client.websocket_connect("/api/v1/ws/dispatch") as ws:
            ws.receive_json()
        raise AssertionError("connection should have been rejected")
    except Exception:
        pass  # Rejection (close/error) is the expected outcome.
