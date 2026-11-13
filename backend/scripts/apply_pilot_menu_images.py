"""Pilot menu image applier.

Reads data/pilot-menu-images.json (one photo per pilot menu item,
Commons hotlinks or repo-hosted generated images) and sets
MenuItem.image_url by (restaurant place_id, item name). Idempotent:
re-running only updates rows whose URL changed.

Only prospect restaurants are touched, mirroring import_pilot_menus.py.
Items marked needs_generation (url null) are skipped.

Usage (from backend/):
    python scripts/apply_pilot_menu_images.py [--path PATH] [--dry-run]

Default path: ../data/pilot-menu-images.json (repo data directory).
A missing file is a warning, not an error, so deploys without the
manifest still start.
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
    "pilot-menu-images.json",
)


def apply_images(db, images: dict, dry_run: bool = False) -> dict:
    counts = {"updated": 0, "unchanged": 0, "skipped": 0, "missing": 0}
    for place_id, items in images.items():
        restaurant = (
            db.query(Restaurant).filter(Restaurant.place_id == place_id).first()
        )
        if restaurant is None or restaurant.status != STATUS_PROSPECT:
            counts["skipped"] += len(items)
            continue
        menus = (
            db.query(Menu)
            .filter(Menu.restaurant_id == restaurant.id, Menu.active.is_(True))
            .all()
        )
        by_name = {}
        for menu in menus:
            for item in menu.items:
                by_name[item.name] = item
        for name, spec in items.items():
            url = spec.get("url")
            if not url:
                counts["skipped"] += 1
                continue
            item = by_name.get(name)
            if item is None:
                counts["missing"] += 1
                continue
            if item.image_url == url:
                counts["unchanged"] += 1
            else:
                item.image_url = url
                counts["updated"] += 1
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
        print(f"pilot menu images file not found at {args.path}; nothing to apply")
        return
    with open(args.path, "r", encoding="utf-8") as f:
        images = json.load(f)["images"]
    db = SessionLocal()
    try:
        counts = apply_images(db, images, dry_run=args.dry_run)
    finally:
        db.close()
    print(
        "pilot menu images: {updated} updated, {unchanged} unchanged, "
        "{skipped} skipped, {missing} items not found".format(**counts)
    )
    if args.dry_run:
        print("(dry run: rolled back)")


if __name__ == "__main__":
    main()
