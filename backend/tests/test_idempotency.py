"""Idempotency (orders + census importer) and prospect visibility tests."""

import os

from tests.conftest import demo_headers, importer_module, place_standard_order


def _available_item(seeded):
    return next(i for i in seeded["items"] if i["available"])


def test_order_idempotency_same_key_returns_same_order(client, seeded):
    customer = demo_headers(client, "customer")
    item = _available_item(seeded)
    body = {
        "restaurant_id": seeded["restaurant_id"],
        "items": [{"menu_item_id": item["id"], "quantity": 1}],
        "fulfillment_type": "standard",
        "delivery_address": {
            "line1": "123 Main St",
            "city": "Denton",
            "state": "TX",
            "postal_code": "76201",
        },
        "tip_cents": 0,
        "channel": "app",
    }
    headers = {**customer, "Idempotency-Key": "order-key-123"}
    first = client.post("/api/v1/orders", json=body, headers=headers)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/orders", json=body, headers=headers)
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["order_number"] == first.json()["order_number"]
    # Only one order exists for the customer.
    mine = client.get("/api/v1/orders", headers=customer).json()
    assert mine["total"] == 1


def test_order_idempotency_different_key_creates_new_order(client, seeded):
    customer = demo_headers(client, "customer")
    item = _available_item(seeded)
    body = {
        "restaurant_id": seeded["restaurant_id"],
        "items": [{"menu_item_id": item["id"], "quantity": 1}],
        "fulfillment_type": "standard",
        "delivery_address": {
            "line1": "123 Main St",
            "city": "Denton",
            "state": "TX",
            "postal_code": "76201",
        },
        "channel": "app",
    }
    first = client.post(
        "/api/v1/orders", json=body, headers={**customer, "Idempotency-Key": "k1"}
    )
    second = client.post(
        "/api/v1/orders", json=body, headers={**customer, "Idempotency-Key": "k2"}
    )
    assert first.json()["id"] != second.json()["id"]


def test_importer_idempotent_and_prospects_hidden(client, seeded):
    admin = demo_headers(client, "admin")
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "data",
        "denton-restaurants.sample.json",
    )
    first = importer_module.run(sample_path)
    assert first == {"created": 3, "updated": 0, "skipped": 1}, first
    second = importer_module.run(sample_path)
    assert second == {"created": 0, "updated": 3, "skipped": 1}, second

    # Prospects are visible only in the admin list.
    admin_list = client.get(
        "/api/v1/admin/restaurants?status=prospect", headers=admin
    ).json()
    assert admin_list["total"] == 3
    assert all(r["status"] == "prospect" for r in admin_list["items"])
    assert all(r["source"] == "census" for r in admin_list["items"])

    # Prospects never appear in the public restaurant list, and neither
    # does the demo restaurant (internal test data, never listed).
    public = client.get("/api/v1/restaurants").json()
    assert public["total"] == 0
    assert public["items"] == []

    # Prospect detail is 404 for the public.
    prospect_id = admin_list["items"][0]["id"]
    assert client.get(f"/api/v1/restaurants/{prospect_id}").status_code == 404
    assert client.get(f"/api/v1/restaurants/{prospect_id}/menu").status_code == 404

    # A prospect cannot be ordered from.
    customer = demo_headers(client, "customer")
    resp = client.post(
        "/api/v1/orders",
        json={
            "restaurant_id": prospect_id,
            "items": [{"menu_item_id": 1, "quantity": 1}],
            "fulfillment_type": "pickup",
        },
        headers=customer,
    )
    assert resp.status_code == 404


def test_importer_dry_run_writes_nothing(client, seeded):
    admin = demo_headers(client, "admin")
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "data",
        "denton-restaurants.sample.json",
    )
    counts = importer_module.run(sample_path, dry_run=True)
    assert counts == {"created": 3, "updated": 0, "skipped": 1}
    admin_list = client.get(
        "/api/v1/admin/restaurants?status=prospect", headers=admin
    ).json()
    assert admin_list["total"] == 0
