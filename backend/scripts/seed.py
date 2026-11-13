"""Seed the MVP slice demo data (contract section 8).

Idempotent: safe to re-run; existing rows are found by their natural keys
and left alone. Never runs automatically on app startup.

Usage (from backend/):
    python scripts/seed.py

Creates:
  - Denton pilot zone (polygon lng -97.20 to -97.05, lat 33.12 to 33.30;
    postal codes 76201, 76203, 76205, 76207, 76208, 76209, 76210; tax 825 bps)
  - Pricing rules per contract section 5
  - ONE demo restaurant "Demo Diner (Denton Pilot)" (status demo) with one
    location, one menu, 6 items (one unavailable)
  - 6 demo users, all with password Demo1234!
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.drivers import Driver, ONBOARDING_APPROVED  # noqa: E402
from app.models.geo import Address, ServiceZone  # noqa: E402
from app.models.identity import (  # noqa: E402
    ALL_ROLES,
    Customer,
    Role,
    User,
    UserRole,
)
from app.models.payments import (  # noqa: E402
    RULE_DRIVER_BASE_PAY,
    RULE_PICKUP_DELIVERY_FEE,
    RULE_RESTAURANT_FULFILLMENT_FEE,
    RULE_STANDARD_DELIVERY_FEE,
    PricingRule,
)
from app.models.restaurants import Menu, MenuItem, Restaurant, RestaurantLocation  # noqa: E402

DEMO_PASSWORD = "Demo1234!"

ZONE_NAME = "Denton"
ZONE_POSTAL_CODES = ["76201", "76203", "76205", "76207", "76208", "76209", "76210"]
ZONE_TAX_BPS = 825
# Rough rectangle around Denton TX (lng -97.20 to -97.05, lat 33.12 to 33.30).
ZONE_BOUNDARY_WKT = (
    "POLYGON((-97.20 33.12, -97.05 33.12, -97.05 33.30, -97.20 33.30, -97.20 33.12))"
)

PRICING_DEFAULTS = {
    RULE_STANDARD_DELIVERY_FEE: 399,
    RULE_PICKUP_DELIVERY_FEE: 0,
    RULE_DRIVER_BASE_PAY: 250,
    RULE_RESTAURANT_FULFILLMENT_FEE: 75,
}

RESTAURANT_NAME = "Demo Diner (Denton Pilot)"

MENU_ITEMS = [
    # name, description, price_cents, category, available, image_url
    # Images live in frontend/public/menu/ (served from the site root).
    ("Margherita Pizza", "Demo item: tomato, mozzarella, basil.", 1080, "Mains", True, "/menu/margherita-pizza.jpg"),
    ("Demo Burger", "Demo item: beef patty, lettuce, tomato, bun.", 1099, "Mains", True, "/menu/demo-burger.jpg"),
    ("Garden Salad", "Demo item: mixed greens, cucumber, dressing.", 899, "Salads", True, "/menu/garden-salad.jpg"),
    ("Chicken Sandwich", "Demo item: grilled chicken, mayo, bun.", 1199, "Mains", True, "/menu/chicken-sandwich.jpg"),
    ("Fries", "Demo item: golden fries with salt.", 399, "Sides", True, "/menu/fries.jpg"),
    ("Iced Tea", "Demo item: brewed iced tea.", 299, "Drinks", False, "/menu/iced-tea.jpg"),  # unavailable
]

DEMO_USERS = [
    # email, full_name, role, scoped to demo restaurant?
    ("customer@demo.commontable.local", "Demo Customer", "customer", False),
    ("owner@demo.commontable.local", "Demo Owner", "restaurant_owner", True),
    ("staff@demo.commontable.local", "Demo Staff", "restaurant_staff", True),
    ("driver@demo.commontable.local", "Demo Driver", "driver", False),
    ("dispatch@demo.commontable.local", "Demo Dispatcher", "dispatcher", False),
    ("admin@demo.commontable.local", "Demo Admin", "admin", False),
]


def seed_roles(db) -> dict[str, Role]:
    roles = {}
    for name in ALL_ROLES:
        role = db.query(Role).filter(Role.name == name).first()
        if role is None:
            role = Role(name=name, description=f"{name} role")
            db.add(role)
            db.flush()
        roles[name] = role
    return roles


def seed_zone(db) -> ServiceZone:
    zone = db.query(ServiceZone).filter(ServiceZone.name == ZONE_NAME).first()
    if zone is None:
        zone = ServiceZone(
            name=ZONE_NAME,
            boundary=ZONE_BOUNDARY_WKT,
            postal_codes=ZONE_POSTAL_CODES,
            tax_rate_bps=ZONE_TAX_BPS,
            active=True,
        )
        db.add(zone)
        db.flush()
    return zone


def seed_pricing(db, zone: ServiceZone) -> None:
    for key, value in PRICING_DEFAULTS.items():
        rule = (
            db.query(PricingRule)
            .filter(
                PricingRule.rule_key == key,
                PricingRule.service_zone_id == zone.id,
            )
            .first()
        )
        if rule is None:
            db.add(
                PricingRule(
                    service_zone_id=zone.id,
                    rule_key=key,
                    value_cents=value,
                    active=True,
                )
            )
    db.flush()


def seed_restaurant(db, zone: ServiceZone) -> Restaurant:
    restaurant = (
        db.query(Restaurant).filter(Restaurant.name == RESTAURANT_NAME).first()
    )
    if restaurant is None:
        restaurant = Restaurant(
            name=RESTAURANT_NAME,
            description="Demo restaurant for the Denton pilot. Not a real restaurant.",
            phone="(940) 555-0100",
            email="demo@demo.commontable.local",
            status="demo",
            direct2door_enabled=True,
            source="seed",
        )
        db.add(restaurant)
        db.flush()

    location = (
        db.query(RestaurantLocation)
        .filter(RestaurantLocation.restaurant_id == restaurant.id)
        .first()
    )
    if location is None:
        address = Address(
            user_id=None,
            line1="100 Demo Street",
            city="Denton",
            state="TX",
            postal_code="76201",
            location="POINT(-97.13 33.21)",
        )
        db.add(address)
        db.flush()
        db.add(
            RestaurantLocation(
                restaurant_id=restaurant.id,
                address_id=address.id,
                hours_json={"mon-sun": "11:00-21:00"},
                service_zone_ids=[zone.id],
                latitude=33.21,
                longitude=-97.13,
            )
        )
        db.flush()

    menu = (
        db.query(Menu)
        .filter(Menu.restaurant_id == restaurant.id, Menu.name == "Main Menu")
        .first()
    )
    if menu is None:
        menu = Menu(restaurant_id=restaurant.id, name="Main Menu", active=True)
        db.add(menu)
        db.flush()

    for name, description, price_cents, category, available, image_url in MENU_ITEMS:
        item = (
            db.query(MenuItem)
            .filter(MenuItem.menu_id == menu.id, MenuItem.name == name)
            .first()
        )
        if item is None:
            db.add(
                MenuItem(
                    menu_id=menu.id,
                    name=name,
                    description=description,
                    price_cents=price_cents,
                    category=category,
                    available=available,
                    image_url=image_url,
                )
            )
        elif not item.image_url:
            # Backfill images on items seeded before image_url existed.
            item.image_url = image_url
    db.flush()
    return restaurant


def seed_users(db, roles: dict[str, Role], restaurant: Restaurant) -> None:
    password_hash = hash_password(DEMO_PASSWORD)
    for email, full_name, role_name, scoped in DEMO_USERS:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                full_name=full_name,
                password_hash=password_hash,
            )
            db.add(user)
            db.flush()
        scope_id = restaurant.id if scoped else None
        grant = (
            db.query(UserRole)
            .filter(
                UserRole.user_id == user.id,
                UserRole.role_id == roles[role_name].id,
                UserRole.scope_id == scope_id,
            )
            .first()
        )
        if grant is None:
            db.add(
                UserRole(
                    user_id=user.id,
                    role_id=roles[role_name].id,
                    scope_type="restaurant" if scope_id is not None else None,
                    scope_id=scope_id,
                )
            )
        if role_name == "customer":
            if db.query(Customer).filter(Customer.user_id == user.id).first() is None:
                db.add(Customer(user_id=user.id))
        if role_name == "driver":
            driver = db.query(Driver).filter(Driver.user_id == user.id).first()
            if driver is None:
                db.add(
                    Driver(
                        user_id=user.id,
                        onboarding_status=ONBOARDING_APPROVED,
                        license_verified=True,
                    )
                )
            elif driver.onboarding_status != ONBOARDING_APPROVED:
                driver.onboarding_status = ONBOARDING_APPROVED
    db.flush()


def main() -> None:
    db = SessionLocal()
    try:
        roles = seed_roles(db)
        zone = seed_zone(db)
        seed_pricing(db, zone)
        restaurant = seed_restaurant(db, zone)
        seed_users(db, roles, restaurant)
        db.commit()
        print(f"Seeded zone: {zone.name} (id={zone.id})")
        print(f"Seeded restaurant: {restaurant.name} (id={restaurant.id})")
        print("Seeded demo users (password Demo1234!):")
        for email, _, role_name, _ in DEMO_USERS:
            print(f"  {email} ({role_name})")
        print("Seed complete. Re-running is safe (idempotent).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
