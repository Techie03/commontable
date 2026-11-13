"""Coming-soon directory: prospects are listed (read-only, not orderable),
filtered by postal code, and never leak into the public orderable list."""

from app.db.session import SessionLocal
from app.models.geo import Address
from app.models.restaurants import Restaurant, RestaurantLocation


def _make_prospect(db, name, postal_code, category="Mexican"):
    restaurant = Restaurant(
        name=name,
        status="prospect",
        source="census",
        primary_category=category,
        phone="940-555-0100",
    )
    db.add(restaurant)
    db.flush()
    address = Address(
        user_id=None,
        line1="100 Test St",
        city="Denton",
        state="TX",
        postal_code=postal_code,
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
    db.flush()
    return restaurant


def test_coming_soon_lists_prospects(client, seeded):
    db = SessionLocal()
    try:
        _make_prospect(db, "Test Taqueria", "76201")
        _make_prospect(db, "Test Bistro", "76205", category="American")
        db.commit()
    finally:
        db.close()

    res = client.get("/api/v1/restaurants/coming-soon")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2
    names = {r["name"] for r in body["items"]}
    assert names == {"Test Taqueria", "Test Bistro"}
    assert all(r["status"] == "prospect" for r in body["items"])


def test_coming_soon_filters_by_postal_code(client, seeded):
    db = SessionLocal()
    try:
        _make_prospect(db, "Test Taqueria", "76201")
        _make_prospect(db, "Test Bistro", "76205", category="American")
        db.commit()
    finally:
        db.close()

    res = client.get("/api/v1/restaurants/coming-soon?postal_code=76201")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Test Taqueria"


def test_public_list_still_excludes_prospects(client, seeded):
    db = SessionLocal()
    try:
        _make_prospect(db, "Test Taqueria", "76201")
        db.commit()
    finally:
        db.close()

    res = client.get("/api/v1/restaurants")
    assert res.status_code == 200, res.text
    names = {r["name"] for r in res.json()["items"]}
    assert "Test Taqueria" not in names
    assert "Demo Diner (Denton Pilot)" in names
