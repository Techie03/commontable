"""Pilot browse-only menus + Demo Diner removal from public surfaces.

Covers: browse-menu serves prospect menus only; the demo restaurant is
invisible to anonymous customers (list/detail/menu) while staff scoped
to it still open its dashboard and menu; coming-soon carries a
has_menu flag; a prospect with a menu still cannot be ordered from.
"""

from app.db.session import SessionLocal
from app.models.geo import Address
from app.models.restaurants import (
    Menu,
    MenuItem,
    Restaurant,
    RestaurantLocation,
)
from tests.conftest import demo_headers, place_standard_order


def _make_prospect_with_menu(db, name="Pilot Taqueria", with_menu=True):
    restaurant = Restaurant(
        name=name,
        status="prospect",
        source="census",
        primary_category="Mexican",
        phone="940-555-0100",
        website="https://example.com/pilot",
    )
    db.add(restaurant)
    db.flush()
    address = Address(
        user_id=None,
        line1="100 Test St",
        city="Denton",
        state="TX",
        postal_code="76201",
    )
    db.add(address)
    db.flush()
    db.add(
        RestaurantLocation(
            restaurant_id=restaurant.id,
            address_id=address.id,
            service_zone_ids=[],
            latitude=33.21,
            longitude=-97.13,
        )
    )
    item_id = None
    if with_menu:
        menu = Menu(restaurant_id=restaurant.id, name="Main Menu", active=True)
        db.add(menu)
        db.flush()
        item = MenuItem(
            menu_id=menu.id,
            name="Test Taco",
            description="A real taco.",
            price_cents=999,
            category="Mains",
            available=True,
            image_url="https://example.com/taco.jpg",
        )
        db.add(item)
        db.flush()
        item_id = item.id
        unpriced = MenuItem(
            menu_id=menu.id,
            name="Mystery Special",
            description=None,
            price_cents=0,
            category="Mains",
            available=True,
        )
        db.add(unpriced)
    db.commit()
    return restaurant.id, item_id


def test_browse_menu_serves_prospect_menu(client, seeded):
    db = SessionLocal()
    try:
        prospect_id, _ = _make_prospect_with_menu(db)
    finally:
        db.close()
    res = client.get(f"/api/v1/restaurants/{prospect_id}/browse-menu")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["browse_only"] is True
    assert body["name"] == "Pilot Taqueria"
    assert body["website"] == "https://example.com/pilot"
    names = {i["name"] for i in body["items"]}
    assert names == {"Test Taco", "Mystery Special"}
    unpriced = [i for i in body["items"] if i["name"] == "Mystery Special"][0]
    assert unpriced["price_cents"] == 0


def test_browse_menu_empty_for_prospect_without_menu(client, seeded):
    db = SessionLocal()
    try:
        prospect_id, _ = _make_prospect_with_menu(db, with_menu=False)
    finally:
        db.close()
    res = client.get(f"/api/v1/restaurants/{prospect_id}/browse-menu")
    assert res.status_code == 200, res.text
    assert res.json()["items"] == []
    assert res.json()["menus"] == []


def test_browse_menu_404_for_demo_and_missing(client, seeded):
    demo_id = seeded["restaurant_id"]
    assert (
        client.get(f"/api/v1/restaurants/{demo_id}/browse-menu").status_code == 404
    )
    assert client.get("/api/v1/restaurants/999999/browse-menu").status_code == 404


def test_demo_invisible_to_public_but_open_to_scoped_staff(client, seeded):
    demo_id = seeded["restaurant_id"]
    # Anonymous: not listed, no detail, no menu.
    public = client.get("/api/v1/restaurants").json()
    assert all(r["id"] != demo_id for r in public["items"])
    assert client.get(f"/api/v1/restaurants/{demo_id}").status_code == 404
    assert client.get(f"/api/v1/restaurants/{demo_id}/menu").status_code == 404
    # The owner scoped to it still opens its dashboard and menu.
    owner = demo_headers(client, "owner")
    detail = client.get(f"/api/v1/restaurants/{demo_id}", headers=owner)
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "Demo Diner (Denton Pilot)"
    menu = client.get(f"/api/v1/restaurants/{demo_id}/menu", headers=owner)
    assert menu.status_code == 200, menu.text
    assert len(menu.json()["items"]) > 0
    # An unrelated customer still gets 404.
    customer = demo_headers(client, "customer")
    assert (
        client.get(f"/api/v1/restaurants/{demo_id}", headers=customer).status_code
        == 404
    )


def test_coming_soon_has_menu_flag(client, seeded):
    db = SessionLocal()
    try:
        with_menu_id, _ = _make_prospect_with_menu(db, name="With Menu")
        without_menu_id, _ = _make_prospect_with_menu(
            db, name="Without Menu", with_menu=False
        )
    finally:
        db.close()
    res = client.get("/api/v1/restaurants/coming-soon?page_size=100")
    assert res.status_code == 200, res.text
    by_id = {r["id"]: r for r in res.json()["items"]}
    assert by_id[with_menu_id]["has_menu"] is True
    assert by_id[with_menu_id]["card_image_url"] == "https://example.com/taco.jpg"
    assert by_id[without_menu_id]["has_menu"] is False
    assert by_id[without_menu_id]["card_image_url"] is None


def test_prospect_with_menu_still_not_orderable(client, seeded):
    db = SessionLocal()
    try:
        prospect_id, item_id = _make_prospect_with_menu(db)
    finally:
        db.close()
    customer = demo_headers(client, "customer")
    resp = place_standard_order(client, customer, prospect_id, item_id)
    assert resp.status_code == 404, resp.text
