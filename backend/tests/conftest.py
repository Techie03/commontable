"""Pytest setup: SQLite database, seeded demo data, auth helpers.

DATABASE_URL is overridden to SQLite BEFORE any app module is imported, so
the app's engine (created at import time) points at the test database.
"""

import importlib.util
import os
import sys

# Must run before any `app` import.
os.environ["DATABASE_URL"] = "sqlite:////tmp/commontable_test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.db.session import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402,F401
from main import create_app  # noqa: E402

TEST_DB_PATH = "/tmp/commontable_test.db"


def _load_script(name: str):
    path = os.path.join(BACKEND_DIR, "scripts", f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed_module = _load_script("seed")
importer_module = _load_script("import_denton_restaurants")


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    Base.metadata.create_all(engine)
    yield
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture(autouse=True)
def _clean_db():
    yield
    db = SessionLocal()
    try:
        # FK checks are off, so deletion order does not matter; avoid
        # sorted_tables (it warns about the orders/payments FK cycle).
        db.execute(text("PRAGMA foreign_keys=OFF"))
        for table in reversed(list(Base.metadata.tables.values())):
            db.execute(table.delete())
        db.execute(text("PRAGMA foreign_keys=ON"))
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def client():
    return TestClient(create_app())


@pytest.fixture()
def seeded():
    """Run the real seed script functions into the test DB."""
    db = SessionLocal()
    try:
        roles = seed_module.seed_roles(db)
        zone = seed_module.seed_zone(db)
        seed_module.seed_pricing(db, zone)
        restaurant = seed_module.seed_restaurant(db, zone)
        seed_module.seed_users(db, roles, restaurant)
        db.commit()
        from app.models.restaurants import MenuItem

        items = (
            db.query(MenuItem)
            .join(MenuItem.menu)
            .filter(MenuItem.menu.has(restaurant_id=restaurant.id))
            .order_by(MenuItem.id)
            .all()
        )
        from app.models.drivers import Driver

        driver = db.query(Driver).first()
        return {
            "zone_id": zone.id,
            "restaurant_id": restaurant.id,
            "items": [
                {
                    "id": i.id,
                    "name": i.name,
                    "price_cents": i.price_cents,
                    "available": i.available,
                }
                for i in items
            ],
            "driver_id": driver.id if driver else None,
        }
    finally:
        db.close()


DEMO_PASSWORD = "Demo1234!"
DEMO_EMAILS = {
    "customer": "customer@demo.commontable.local",
    "owner": "owner@demo.commontable.local",
    "staff": "staff@demo.commontable.local",
    "driver": "driver@demo.commontable.local",
    "dispatch": "dispatch@demo.commontable.local",
    "admin": "admin@demo.commontable.local",
}


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> dict:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def demo_headers(client: TestClient, who: str) -> dict:
    return auth_headers(login(client, DEMO_EMAILS[who])["access_token"])


def demo_token(client: TestClient, who: str) -> str:
    return login(client, DEMO_EMAILS[who])["access_token"]


def place_standard_order(client, headers, restaurant_id, item_id, **overrides):
    body = {
        "restaurant_id": restaurant_id,
        "items": [{"menu_item_id": item_id, "quantity": 1}],
        "fulfillment_type": "standard",
        "delivery_address": {
            "line1": "123 Main St",
            "city": "Denton",
            "state": "TX",
            "postal_code": "76201",
        },
        "tip_cents": 100,
        "channel": "app",
    }
    body.update(overrides)
    return client.post("/api/v1/orders", json=body, headers=headers)
