"""Denton restaurant census importer (contract section 8.1).

Reads the Google Maps census JSON (schema: place_id, name, address,
city/state/zip, latitude/longitude, phone, website, primary_category,
secondary_categories, price_level, rating_avg, rating_count, hours,
maps_search_url) and upserts restaurants idempotently keyed by place_id.

Imported restaurants get status "prospect" and source "census": they are
unclaimed, not onboarded, NOT orderable, and never presented as partners.
Each gets one location + address and no menu.

Usage (from backend/):
    python scripts/import_denton_restaurants.py [--path PATH] [--dry-run]

Default path: ../data/denton-restaurants.json (repo data directory).
Prints created / updated / skipped counts.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.models.geo import Address  # noqa: E402
from app.models.restaurants import Restaurant, RestaurantLocation  # noqa: E402

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..",
    "data",
    "denton-restaurants.json",
)


def load_entries(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # Accept a wrapper object with a "restaurants" list.
        entries = data.get("restaurants") or data.get("entries") or []
    else:
        entries = data
    if not isinstance(entries, list):
        raise ValueError("Census file must be a JSON list of restaurant entries")
    return entries


PRICE_LEVEL_LABELS = {
    "inexpensive": 1,
    "moderate": 2,
    "expensive": 3,
    "very expensive": 4,
}


def normalize_price_level(value) -> int | None:
    """Map the census price level to the 1-4 integer scale.

    The census JSON carries labels ("inexpensive" .. "very expensive") or
    null; the sample file and some records carry integers already.
    Unknown values become None rather than failing the import.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 4 else None
    if isinstance(value, str):
        return PRICE_LEVEL_LABELS.get(value.strip().lower())
    return None


def normalize_postal_code(value) -> str:
    """Normalize a ZIP code to 5 digits (ZIP+4 like 76201-1629 -> 76201)."""
    text = str(value or "").strip()
    return text[:5] if len(text) >= 5 and text[:5].isdigit() else text


def upsert_restaurant(db, entry: dict) -> str:
    """Upsert one census entry. Returns 'created', 'updated', or 'skipped'."""
    place_id = entry.get("place_id")
    name = entry.get("name")
    if not place_id or not name:
        return "skipped"

    restaurant = (
        db.query(Restaurant).filter(Restaurant.place_id == place_id).first()
    )
    created = restaurant is None
    if created:
        restaurant = Restaurant(place_id=place_id, name=name)
        # Prospects are set ONLY on create: a re-import must never demote a
        # restaurant that has since onboarded (pending/active) back to prospect.
        restaurant.status = "prospect"
        restaurant.source = "census"
        db.add(restaurant)
    # Census fields are refreshed on every run; status/source are preserved
    # on update so onboarding progress survives a re-import.
    restaurant.name = name
    restaurant.phone = entry.get("phone")
    restaurant.website = entry.get("website")
    restaurant.primary_category = entry.get("primary_category")
    restaurant.price_level = normalize_price_level(entry.get("price_level"))
    restaurant.rating_avg = entry.get("rating_avg")
    restaurant.rating_count = entry.get("rating_count")
    restaurant.maps_search_url = entry.get("maps_search_url")
    db.flush()

    location = (
        db.query(RestaurantLocation)
        .filter(RestaurantLocation.restaurant_id == restaurant.id)
        .first()
    )
    address_text = entry.get("address") or ""
    city = entry.get("city") or "Denton"
    state = entry.get("state") or "TX"
    zip_code = normalize_postal_code(
        entry.get("zip") or entry.get("postal_code") or ""
    )
    latitude = entry.get("latitude")
    longitude = entry.get("longitude")
    hours = entry.get("hours")
    if location is None:
        address = Address(
            user_id=None,
            line1=address_text,
            city=city,
            state=state,
            postal_code=str(zip_code),
        )
        db.add(address)
        db.flush()
        db.add(
            RestaurantLocation(
                restaurant_id=restaurant.id,
                address_id=address.id,
                hours_json=hours if isinstance(hours, dict) else None,
                service_zone_ids=[],
                latitude=latitude,
                longitude=longitude,
            )
        )
    else:
        address = location.address
        if address is not None:
            address.line1 = address_text
            address.city = city
            address.state = state
            address.postal_code = str(zip_code)
        location.latitude = latitude
        location.longitude = longitude
        if isinstance(hours, dict):
            location.hours_json = hours
    db.flush()
    return "created" if created else "updated"


def run(path: str, dry_run: bool = False) -> dict:
    entries = load_entries(path)
    counts = {"created": 0, "updated": 0, "skipped": 0}
    db = SessionLocal()
    try:
        for entry in entries:
            result = upsert_restaurant(db, entry)
            counts[result] += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the Denton restaurant census as prospect restaurants."
    )
    parser.add_argument(
        "--path",
        default=DEFAULT_PATH,
        help="Path to the census JSON file (default: ../data/denton-restaurants.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count without writing anything",
    )
    args = parser.parse_args()
    if not os.path.exists(args.path):
        print(f"Census file not found: {args.path}")
        print("Nothing imported. The census file is delivered separately.")
        sys.exit(1)
    counts = run(args.path, dry_run=args.dry_run)
    mode = " (dry run, nothing written)" if args.dry_run else ""
    print(
        f"Census import{mode}: created={counts['created']} "
        f"updated={counts['updated']} skipped={counts['skipped']}"
    )


if __name__ == "__main__":
    main()
