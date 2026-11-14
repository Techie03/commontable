"""Restaurants and menus router (public browsing + staff management)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_user,
    get_optional_user,
    has_restaurant_access,
    is_admin,
    require_restaurant_access,
)
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.db.session import get_db
from app.models.geo import Address, ServiceZone
from app.models.identity import (
    RESTAURANT_ROLES,
    ROLE_RESTAURANT_MANAGER,
    ROLE_RESTAURANT_OWNER,
    ROLE_RESTAURANT_STAFF,
    Role,
    User,
    UserRole,
)
from app.models.orders import Order
from app.models.payments import ENTRY_RESTAURANT_PAYABLE, LedgerEntry
from app.models.restaurants import (
    PUBLIC_STATUSES,
    STATUS_PENDING,
    STATUS_PROSPECT,
    Menu,
    MenuItem,
    Modifier,
    Restaurant,
    RestaurantLocation,
)
from app.schemas.orders import OrderOut, order_to_out
from app.schemas.restaurants import (
    LocationIn,
    MenuItemCreate,
    MenuItemOut,
    MenuItemUpdate,
    MenuOut,
    RestaurantCreate,
    RestaurantOut,
    RestaurantUpdate,
    location_to_out,
    menu_item_to_out,
    restaurant_to_out,
)

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


def _paginate(query, page: int, page_size: int):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.get("", response_model=dict)
def list_restaurants(
    zone_id: int | None = None,
    postal_code: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Public list. Only active restaurants, ever. Demo restaurants are
    internal test data, never listed. Prospect (census, unclaimed)
    restaurants are never listed and never orderable."""
    query = (
        db.query(Restaurant)
        .filter(Restaurant.status.in_(PUBLIC_STATUSES))
        .order_by(Restaurant.name)
    )
    restaurants = query.all()
    if zone_id is not None:
        restaurants = [
            r
            for r in restaurants
            if any(zone_id in (loc.service_zone_ids or []) for loc in r.locations)
        ]
    if postal_code is not None:
        zones = db.query(ServiceZone).filter(ServiceZone.active.is_(True)).all()
        zone_ids = {z.id for z in zones if postal_code in (z.postal_codes or [])}
        restaurants = [
            r
            for r in restaurants
            if any(
                set(loc.service_zone_ids or []) & zone_ids for loc in r.locations
            )
        ]
    total = len(restaurants)
    sliced = restaurants[(page - 1) * page_size : page * page_size]
    return {
        "items": [restaurant_to_out(r) for r in sliced],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/coming-soon", response_model=dict)
def list_coming_soon(
    postal_code: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Public directory of prospect (census, unclaimed) restaurants.

    Read-only discovery only: these restaurants have NOT joined
    CommonTable and are NOT orderable. They are listed as coming soon,
    never presented as partners. Must stay above the /{restaurant_id}
    route or FastAPI matches "coming-soon" as an id.
    """
    restaurants = (
        db.query(Restaurant)
        .filter(Restaurant.status == STATUS_PROSPECT)
        .order_by(Restaurant.name)
        .all()
    )
    if postal_code is not None:
        restaurants = [
            r
            for r in restaurants
            if any(
                loc.address is not None
                and loc.address.postal_code == postal_code
                for loc in r.locations
            )
        ]
    total = len(restaurants)
    sliced = restaurants[(page - 1) * page_size : page * page_size]
    # Pilot restaurants with a collected menu get a "View menu" link; the
    # flag is one query for the whole page, not one per restaurant.
    menu_restaurant_ids = {
        rid
        for (rid,) in db.query(Menu.restaurant_id)
        .join(MenuItem, MenuItem.menu_id == Menu.id)
        .filter(Menu.active.is_(True))
        .distinct()
        .all()
    }
    # Card photo for pilot restaurants: the first menu item photo, one
    # query for the whole page.
    card_images: dict[int, str] = {}
    if sliced:
        rows = (
            db.query(Menu.restaurant_id, MenuItem.image_url)
            .join(MenuItem, MenuItem.menu_id == Menu.id)
            .filter(
                Menu.restaurant_id.in_([r.id for r in sliced]),
                Menu.active.is_(True),
                MenuItem.image_url.isnot(None),
                MenuItem.image_url != "",
            )
            .order_by(MenuItem.id)
            .all()
        )
        for rid, url in rows:
            card_images.setdefault(rid, url)
    items = []
    for r in sliced:
        d = restaurant_to_out(r).model_dump()
        d["has_menu"] = r.id in menu_restaurant_ids
        d["card_image_url"] = card_images.get(r.id)
        items.append(d)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{restaurant_id}", response_model=RestaurantOut)
def get_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Restaurant detail. Customers see active restaurants; staff scoped
    to a restaurant (and admins) also see theirs whatever its status, so
    the restaurant dashboard keeps working for test restaurants."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    if restaurant.status not in PUBLIC_STATUSES and not has_restaurant_access(
        restaurant_id, user
    ):
        raise not_found("Restaurant not found")
    return restaurant_to_out(restaurant)


@router.get("/{restaurant_id}/menu")
def get_menu(
    restaurant_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Menu items under the "items" key (contract coordination note 6).

    Customers see active restaurants' menus; staff scoped to a
    restaurant (and admins) also see theirs whatever its status, so the
    restaurant menu page keeps working for test restaurants. Prospect
    menus are browse-only and served by browse-menu instead.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    if restaurant.status not in PUBLIC_STATUSES and not has_restaurant_access(
        restaurant_id, user
    ):
        raise not_found("Restaurant not found")
    menus = (
        db.query(Menu)
        .filter(Menu.restaurant_id == restaurant.id, Menu.active.is_(True))
        .all()
    )
    items = []
    for menu in menus:
        items.extend(menu_item_to_out(item) for item in menu.items)
    return {
        "restaurant_id": restaurant.id,
        "menus": [
            MenuOut(
                id=m.id,
                name=m.name,
                active=m.active,
                items=[menu_item_to_out(i) for i in m.items],
            )
            for m in menus
        ],
        "items": items,
    }


@router.get("/{restaurant_id}/browse-menu")
def get_browse_menu(restaurant_id: int, db: Session = Depends(get_db)):
    """Browse-only menu for a prospect (coming soon) restaurant.

    The restaurant has NOT joined CommonTable: its menu was collected
    from its own published menu and is shown for browsing only. Ordering
    is impossible: place_order rejects non-orderable statuses, and
    prospects never appear in the public restaurant list. Items with
    price_cents 0 have no published price; the UI shows "Price not
    listed" for those.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None or restaurant.status != STATUS_PROSPECT:
        raise not_found("Restaurant not found")
    menus = (
        db.query(Menu)
        .filter(Menu.restaurant_id == restaurant.id, Menu.active.is_(True))
        .all()
    )
    items = []
    for menu in menus:
        items.extend(menu_item_to_out(item) for item in menu.items)
    return {
        "restaurant_id": restaurant.id,
        "name": restaurant.name,
        "website": restaurant.website,
        "primary_category": restaurant.primary_category,
        "phone": restaurant.phone,
        "locations": [location_to_out(loc) for loc in restaurant.locations],
        "browse_only": True,
        "menus": [
            MenuOut(
                id=m.id,
                name=m.name,
                active=m.active,
                items=[menu_item_to_out(i) for i in m.items],
            )
            for m in menus
        ],
        "items": items,
    }


@router.post("", response_model=RestaurantOut, status_code=201)
def create_restaurant(
    body: RestaurantCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Onboarding application. Creates a pending restaurant and grants the
    creator the restaurant_owner role scoped to it."""
    restaurant = Restaurant(
        owner_user_id=user.id,
        name=body.name,
        brand_name=body.brand_name,
        description=body.description,
        phone=body.phone,
        email=body.email,
        status=STATUS_PENDING,
        direct2door_enabled=body.direct2door_enabled,
        website=body.website,
        source="manual",
    )
    db.add(restaurant)
    db.flush()
    role = db.query(Role).filter(Role.name == ROLE_RESTAURANT_OWNER).first()
    if role is not None:
        db.add(
            UserRole(
                user_id=user.id,
                role_id=role.id,
                scope_type="restaurant",
                scope_id=restaurant.id,
                granted_by=user.id,
            )
        )
    db.commit()
    db.refresh(restaurant)
    return restaurant_to_out(restaurant)


@router.patch("/{restaurant_id}", response_model=RestaurantOut)
def update_restaurant(
    restaurant_id: int,
    body: RestaurantUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    require_restaurant_access(
        restaurant_id, user, [ROLE_RESTAURANT_OWNER, ROLE_RESTAURANT_MANAGER]
    )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    db.commit()
    db.refresh(restaurant)
    return restaurant_to_out(restaurant)


@router.post("/{restaurant_id}/locations", status_code=201)
def add_location(
    restaurant_id: int,
    body: LocationIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    require_restaurant_access(
        restaurant_id, user, [ROLE_RESTAURANT_OWNER, ROLE_RESTAURANT_MANAGER]
    )
    address = Address(
        user_id=None,
        line1=body.address.line1,
        line2=body.address.line2,
        city=body.address.city,
        state=body.address.state,
        postal_code=body.address.postal_code,
    )
    db.add(address)
    db.flush()
    location = RestaurantLocation(
        restaurant_id=restaurant.id,
        address_id=address.id,
        hours_json=body.hours_json,
        service_zone_ids=body.service_zone_ids,
        latitude=body.latitude,
        longitude=body.longitude,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location_to_out(location)


@router.post("/{restaurant_id}/menu/items", response_model=MenuItemOut, status_code=201)
def create_menu_item(
    restaurant_id: int,
    body: MenuItemCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    require_restaurant_access(
        restaurant_id, user, [ROLE_RESTAURANT_OWNER, ROLE_RESTAURANT_MANAGER]
    )
    if body.menu_id is not None:
        menu = (
            db.query(Menu)
            .filter(Menu.id == body.menu_id, Menu.restaurant_id == restaurant.id)
            .first()
        )
        if menu is None:
            raise bad_request("Menu not found for this restaurant")
    else:
        menu = (
            db.query(Menu)
            .filter(Menu.restaurant_id == restaurant.id, Menu.active.is_(True))
            .first()
        )
        if menu is None:
            raise bad_request("This restaurant has no active menu yet")
    item = MenuItem(
        menu_id=menu.id,
        name=body.name,
        description=body.description,
        price_cents=body.price_cents,
        category=body.category,
        available=body.available,
        image_url=body.image_url,
    )
    db.add(item)
    db.flush()
    for mod in body.modifiers:
        db.add(
            Modifier(
                menu_item_id=item.id,
                name=mod.name,
                price_delta_cents=mod.price_delta_cents,
                required=mod.required,
                max_selections=mod.max_selections,
            )
        )
    db.commit()
    db.refresh(item)
    return menu_item_to_out(item)


@router.patch("/{restaurant_id}/menu/items/{item_id}", response_model=MenuItemOut)
def update_menu_item(
    restaurant_id: int,
    item_id: int,
    body: MenuItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    item = (
        db.query(MenuItem)
        .join(Menu)
        .filter(MenuItem.id == item_id, Menu.restaurant_id == restaurant.id)
        .first()
    )
    if item is None:
        raise not_found("Menu item not found")
    is_staff_only = user.has_role(ROLE_RESTAURANT_STAFF, scope_id=restaurant_id) and not (
        is_admin(user)
        or user.has_role(
            ROLE_RESTAURANT_OWNER, ROLE_RESTAURANT_MANAGER, scope_id=restaurant_id
        )
    )
    if is_staff_only:
        # Staff may change availability only (spec section 4).
        changed = set(body.model_dump(exclude_unset=True).keys())
        if not changed.issubset({"available"}):
            raise forbidden("Staff can only change item availability")
    else:
        require_restaurant_access(restaurant_id, user, RESTAURANT_ROLES)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return menu_item_to_out(item)


@router.delete("/{restaurant_id}/menu/items/{item_id}")
def delete_menu_item(
    restaurant_id: int,
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.orders import OrderItem

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    require_restaurant_access(
        restaurant_id, user, [ROLE_RESTAURANT_OWNER, ROLE_RESTAURANT_MANAGER]
    )
    item = (
        db.query(MenuItem)
        .join(Menu)
        .filter(MenuItem.id == item_id, Menu.restaurant_id == restaurant.id)
        .first()
    )
    if item is None:
        raise not_found("Menu item not found")
    on_order = (
        db.query(OrderItem).filter(OrderItem.menu_item_id == item.id).first()
    )
    if on_order is not None:
        raise conflict("This item is on an order and cannot be deleted")
    db.delete(item)
    db.commit()
    return {"message": "Menu item deleted"}


@router.get("/{restaurant_id}/orders")
def restaurant_orders(
    restaurant_id: int,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    require_restaurant_access(restaurant_id, user, RESTAURANT_ROLES)
    query = (
        db.query(Order)
        .filter(Order.restaurant_id == restaurant_id)
        .order_by(Order.placed_at.desc(), Order.id.desc())
    )
    if status:
        query = query.filter(Order.status == status)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [order_to_out(o) for o in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{restaurant_id}/reports")
def restaurant_reports(
    restaurant_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise not_found("Restaurant not found")
    require_restaurant_access(
        restaurant_id, user, [ROLE_RESTAURANT_OWNER, ROLE_RESTAURANT_MANAGER]
    )
    orders = db.query(Order).filter(Order.restaurant_id == restaurant_id).all()
    by_status: dict[str, int] = {}
    gross_cents = 0
    for order in orders:
        by_status[order.status] = by_status.get(order.status, 0) + 1
        if order.status not in ("REJECTED", "CANCELLED", "REFUNDED", "FAILED"):
            gross_cents += order.total_cents
    payable = (
        db.query(LedgerEntry)
        .join(Order, LedgerEntry.order_id == Order.id)
        .filter(
            Order.restaurant_id == restaurant_id,
            LedgerEntry.entry_type == ENTRY_RESTAURANT_PAYABLE,
        )
        .all()
    )
    payable_cents = sum(
        e.amount_cents if e.direction == "credit" else -e.amount_cents for e in payable
    )
    return {
        "restaurant_id": restaurant_id,
        "order_count": len(orders),
        "orders_by_status": by_status,
        "gross_cents": gross_cents,
        "settlement": {
            "restaurant_payable_cents": payable_cents,
            "note": "Computed from the ledger. No money has moved.",
        },
    }
