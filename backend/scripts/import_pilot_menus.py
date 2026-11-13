"""Pilot menu importer.

Reads data/pilot-menus.json (real menus collected from each pilot
restaurant's own published menu) and upserts them onto the matching
prospect restaurants, keyed by place_id. Idempotent: re-running updates
in place and prunes items no longer in the file.

Only prospect restaurants are touched. Once a restaurant joins (status
leaves "prospect") its menu is theirs to manage and this importer skips
it, so it can never clobber a restaurant's own edits.

Prices: an item with no published price is stored as price_cents 0.
The browse UI shows "Price not listed" for those; 0 never reaches
checkout because prospects are not orderable (place_order rejects
non-orderable statuses). image_url is never touched here; the image
step sets it separately and re-runs must not wipe it.

Usage (from backend/):
    python scripts/import_pilot_menus.py [--path PATH] [--dry-run]

Default path: ../data/pilot-menus.json (repo data directory).
A missing file is a warning, not an error, so deploys without pilot
menus still start. Prints created / updated / pruned / skipped counts.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.models.restaurants import (  # noqa: E402
    STATUS_PROSPECT,
    Menu,
    MenuItem,
    Restaurant,
)

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..",
    "data",
    "pilot-menus.json",
)

MENU_NAME = "Main Menu"


def load_entries(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["restaurants"]


def import_menus(db, entries: list[dict], dry_run: bool = False) -> dict:
    counts = {"restaurants": 0, "created": 0, "updated": 0, "pruned": 0, "skipped": 0}
    for entry in entries:
        place_id = entry.get("place_id")
        restaurant = (
            db.query(Restaurant).filter(Restaurant.place_id == place_id).first()
        )
        if restaurant is None:
            print(f"  skip {entry.get('name')}: no prospect with place_id {place_id}")
            counts["skipped"] += 1
            continue
        if restaurant.status != STATUS_PROSPECT:
            print(
                f"  skip {restaurant.name}: status is {restaurant.status}, "
                "menu is restaurant-managed now"
            )
            counts["skipped"] += 1
            continue
        counts["restaurants"] += 1
        menu = (
            db.query(Menu)
            .filter(Menu.restaurant_id == restaurant.id, Menu.name == MENU_NAME)
            .first()
        )
        if menu is None:
            menu = Menu(restaurant_id=restaurant.id, name=MENU_NAME, active=True)
            db.add(menu)
            db.flush()
        wanted = {}
        for category in entry.get("categories", []):
            for item in category.get("items", []):
                wanted[item["name"]] = {
                    "description": item.get("description"),
                    "category": category.get("name"),
                    "price_cents": item.get("price_cents") or 0,
                }
        existing = {
            item.name: item
            for item in db.query(MenuItem).filter(MenuItem.menu_id == menu.id).all()
        }
        for name, fields in wanted.items():
            item = existing.get(name)
            if item is None:
                db.add(MenuItem(menu_id=menu.id, name=name, available=True, **fields))
                counts["created"] += 1
            else:
                changed = False
                for key, value in fields.items():
                    if getattr(item, key) != value:
                        setattr(item, key, value)
                        changed = True
                if not item.available:
                    item.available = True
                    changed = True
                if changed:
                    counts["updated"] += 1
        for name, item in existing.items():
            if name not in wanted:
                db.delete(item)
                counts["pruned"] += 1
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not os.path.exists(args.path):
        print(f"pilot menus file not found at {args.path}; nothing to import")
        return
    entries = load_entries(args.path)
    db = SessionLocal()
    try:
        counts = import_menus(db, entries, dry_run=args.dry_run)
    finally:
        db.close()
    print(
        "pilot menus: {restaurants} restaurants, {created} items created, "
        "{updated} updated, {pruned} pruned, {skipped} skipped".format(**counts)
    )
    if args.dry_run:
        print("(dry run: rolled back)")


if __name__ == "__main__":
    main()
