"""Menu onboarding + AI menu features: the first item creates the menu,
bulk add, AI generation (mocked provider), AI photos (mocked provider),
and admin suspend."""

from tests.conftest import demo_headers


def _make_restaurant(client, admin, name="New Test Diner"):
    res = client.post(
        "/api/v1/restaurants",
        json={
            "name": name,
            "phone": "(940) 555-0100",
            "owner_name": "Test Owner",
            "business_address": "1 Test St, Denton, TX 76201",
        },
        headers=admin,
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_first_item_creates_menu(client, seeded):
    admin = demo_headers(client, "admin")
    restaurant = _make_restaurant(client, admin)
    # A new restaurant has no menu at all; the first item must still work.
    res = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/items",
        json={"name": "Test Thali", "price_cents": 1299},
        headers=admin,
    )
    assert res.status_code == 201, res.text
    assert res.json()["name"] == "Test Thali"

    menu = client.get(
        f"/api/v1/restaurants/{restaurant['id']}/menu", headers=admin
    ).json()
    assert len(menu["items"]) == 1
    assert menu["menus"][0]["name"] == "Main Menu"
    assert menu["menus"][0]["active"] is True


def test_bulk_create_items(client, seeded):
    admin = demo_headers(client, "admin")
    restaurant = _make_restaurant(client, admin)
    res = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/items/bulk",
        json={
            "items": [
                {"name": "Item One", "price_cents": 500},
                {"name": "Item Two", "price_cents": 700, "category": "Mains"},
                {"name": "Item Three", "price_cents": 900},
            ]
        },
        headers=admin,
    )
    assert res.status_code == 201, res.text
    assert len(res.json()) == 3

    menu = client.get(
        f"/api/v1/restaurants/{restaurant['id']}/menu", headers=admin
    ).json()
    assert len(menu["items"]) == 3

    # Over the 50-item cap: rejected, nothing saved.
    res = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/items/bulk",
        json={
            "items": [
                {"name": f"Bulk {i}", "price_cents": 100} for i in range(51)
            ]
        },
        headers=admin,
    )
    assert res.status_code == 422, res.text


def test_generate_menu_not_configured(client, seeded, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None)
    admin = demo_headers(client, "admin")
    restaurant = _make_restaurant(client, admin)
    res = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/generate",
        json={"prompt": "South Indian", "item_count": 5},
        headers=admin,
    )
    assert res.status_code == 503, res.text
    assert "not set up" in res.json()["error"]["message"]


def test_generate_menu_with_mocked_service(client, seeded, monkeypatch):
    def fake_generate(*, restaurant_name, prompt, item_count):
        assert restaurant_name == "New Test Diner"
        assert prompt == "South Indian"
        return [
            {
                "name": "Masala Dosa",
                "description": "Crisp crepe, spiced potatoes.",
                "price_cents": 1099,
                "category": "Mains",
            },
            {
                "name": "Filter Coffee",
                "description": "Strong South Indian coffee.",
                "price_cents": 399,
                "category": "Beverages",
            },
        ]

    monkeypatch.setattr(
        "app.api.restaurants.generate_menu_items", fake_generate
    )
    admin = demo_headers(client, "admin")
    restaurant = _make_restaurant(client, admin)
    res = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/generate",
        json={"prompt": "South Indian", "item_count": 5},
        headers=admin,
    )
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert [i["name"] for i in items] == ["Masala Dosa", "Filter Coffee"]
    assert items[0]["price_cents"] == 1099

    # Preview only: nothing was saved.
    menu = client.get(
        f"/api/v1/restaurants/{restaurant['id']}/menu", headers=admin
    ).json()
    assert menu["items"] == []


def test_generate_image_not_configured(client, seeded, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None)
    admin = demo_headers(client, "admin")
    restaurant = _make_restaurant(client, admin)
    item = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/items",
        json={"name": "Test Thali", "price_cents": 1299},
        headers=admin,
    ).json()
    res = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/items/{item['id']}/generate-image",
        headers=admin,
    )
    assert res.status_code == 503, res.text
    assert "not set up" in res.json()["error"]["message"]


def test_generate_image_with_mocked_service(client, seeded, monkeypatch):
    monkeypatch.setattr(
        "app.api.restaurants.generate_food_image",
        lambda *, name, description: b"fake-image-bytes",
    )
    monkeypatch.setattr(
        "app.api.restaurants.upload_menu_image",
        lambda *, image_bytes, filename: "https://example.com/menu/test-thali.png",
    )
    admin = demo_headers(client, "admin")
    restaurant = _make_restaurant(client, admin)
    item = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/items",
        json={"name": "Test Thali", "price_cents": 1299},
        headers=admin,
    ).json()
    res = client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menu/items/{item['id']}/generate-image",
        headers=admin,
    )
    assert res.status_code == 200, res.text
    assert (
        res.json()["image_url"] == "https://example.com/menu/test-thali.png"
    )

    menu = client.get(
        f"/api/v1/restaurants/{restaurant['id']}/menu", headers=admin
    ).json()
    assert menu["items"][0]["image_url"] == (
        "https://example.com/menu/test-thali.png"
    )


def test_suspend_restaurant(client, seeded):
    admin = demo_headers(client, "admin")
    restaurant = _make_restaurant(client, admin)
    res = client.post(
        f"/api/v1/admin/restaurants/{restaurant['id']}/suspend",
        headers=admin,
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "suspended"

    # Suspended restaurants are invisible in every public list.
    soon = client.get("/api/v1/restaurants/coming-soon").json()
    assert all(r["id"] != restaurant["id"] for r in soon["items"])
    public = client.get("/api/v1/restaurants").json()
    assert all(r["id"] != restaurant["id"] for r in public["items"])
