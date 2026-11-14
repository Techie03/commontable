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
    # Demo restaurants are internal test data, never listed publicly.
    assert "Demo Diner (Denton Pilot)" not in names


def _make_pending(db, name, postal_code=None):
    restaurant = Restaurant(
        name=name,
        status="pending",
        source="manual",
        phone="940-555-0100",
    )
    db.add(restaurant)
    db.flush()
    if postal_code is not None:
        address = Address(
            user_id=None,
            line1="200 Test St",
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


def test_coming_soon_includes_pending_signups(client, seeded):
    db = SessionLocal()
    try:
        _make_pending(db, "New Signup Diner")
        db.commit()
    finally:
        db.close()

    # No location yet: visible in the directory for every postal code.
    for query in [
        "/api/v1/restaurants/coming-soon",
        "/api/v1/restaurants/coming-soon?postal_code=76201",
    ]:
        res = client.get(query)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["name"] == "New Signup Diner"
        assert item["status"] == "pending"
        # No public menu link until approved: browse-menu is prospect-only.
        assert item["has_menu"] is False

    # Still never in the orderable public list.
    res = client.get("/api/v1/restaurants")
    assert res.status_code == 200, res.text
    names = {r["name"] for r in res.json()["items"]}
    assert "New Signup Diner" not in names


def test_coming_soon_pending_with_location_filters_by_postal_code(client, seeded):
    db = SessionLocal()
    try:
        _make_pending(db, "Signup Bistro", postal_code="76205")
        db.commit()
    finally:
        db.close()

    res = client.get("/api/v1/restaurants/coming-soon?postal_code=76201")
    assert res.status_code == 200, res.text
    assert res.json()["total"] == 0

    res = client.get("/api/v1/restaurants/coming-soon?postal_code=76205")
    assert res.status_code == 200, res.text
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["name"] == "Signup Bistro"
