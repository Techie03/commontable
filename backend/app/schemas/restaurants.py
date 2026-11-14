"""Restaurant, location, menu, and zone schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AddressIn(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    state: str
    postal_code: str


class AddressOut(BaseModel):
    id: int
    line1: str
    line2: str | None = None
    city: str
    state: str
    postal_code: str
    formatted: str | None = None


class LocationIn(BaseModel):
    address: AddressIn
    hours_json: dict | None = None
    service_zone_ids: list[int] = []
    latitude: float | None = None
    longitude: float | None = None


class LocationOut(BaseModel):
    id: int
    address: AddressOut | None = None
    hours_json: dict | None = None
    service_zone_ids: list[int] = []
    latitude: float | None = None
    longitude: float | None = None
    status: str


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    brand_name: str | None = None
    description: str | None = None
    phone: str = Field(min_length=1, max_length=50)
    email: str | None = None
    direct2door_enabled: bool = False
    website: str | None = None
    # Verification evidence: a restaurant cannot be created without a
    # named owner, a business phone, and a business address. An admin
    # checks these against a public listing before approval.
    owner_name: str = Field(min_length=1, max_length=255)
    business_address: str = Field(min_length=1, max_length=500)
    # Business type (Restaurant, Food Truck, Bakery, ...), from the landing
    # signup form. Optional; shown as the restaurant's category in the feed.
    primary_category: str | None = Field(default=None, max_length=100)


class RestaurantUpdate(BaseModel):
    name: str | None = None
    brand_name: str | None = None
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    direct2door_enabled: bool | None = None
    website: str | None = None
    owner_name: str | None = None
    business_address: str | None = None
    primary_category: str | None = None


class RestaurantVerifyIn(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class RestaurantOut(BaseModel):
    id: int
    name: str
    brand_name: str | None = None
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str
    source: str
    direct2door_enabled: bool
    website: str | None = None
    primary_category: str | None = None
    price_level: int | None = None
    rating_avg: float | None = None
    rating_count: int | None = None
    owner_name: str | None = None
    business_address: str | None = None
    verification_status: str = "unverified"
    verification_notes: str | None = None
    verified_at: datetime | None = None
    locations: list[LocationOut] = []
    created_at: datetime | None = None


class ModifierIn(BaseModel):
    name: str
    price_delta_cents: int = 0
    required: bool = False
    max_selections: int | None = None


class ModifierOut(BaseModel):
    id: int
    name: str
    price_delta_cents: int
    required: bool
    max_selections: int | None = None


class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price_cents: int = Field(ge=0)
    category: str | None = None
    available: bool = True
    image_url: str | None = None
    menu_id: int | None = None
    modifiers: list[ModifierIn] = []


class MenuItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    category: str | None = None
    available: bool | None = None
    image_url: str | None = None


class MenuItemOut(BaseModel):
    id: int
    menu_id: int
    name: str
    description: str | None = None
    price_cents: int
    category: str | None = None
    available: bool
    image_url: str | None = None
    modifiers: list[ModifierOut] = []


class MenuGenerateIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    item_count: int = Field(default=12, ge=1, le=40)


class GeneratedMenuItemOut(BaseModel):
    name: str
    description: str | None = None
    price_cents: int
    category: str | None = None


class MenuGenerateOut(BaseModel):
    items: list[GeneratedMenuItemOut]


class BulkMenuItemsIn(BaseModel):
    items: list[MenuItemCreate] = Field(min_length=1, max_length=50)


class GenerateImageOut(BaseModel):
    image_url: str


class MenuOut(BaseModel):
    id: int
    name: str
    active: bool
    items: list[MenuItemOut] = []


def address_to_out(address) -> AddressOut | None:
    if address is None:
        return None
    return AddressOut(
        id=address.id,
        line1=address.line1,
        line2=address.line2,
        city=address.city,
        state=address.state,
        postal_code=address.postal_code,
        formatted=address.formatted(),
    )


def location_to_out(location) -> LocationOut:
    return LocationOut(
        id=location.id,
        address=address_to_out(location.address),
        hours_json=location.hours_json,
        service_zone_ids=location.service_zone_ids or [],
        latitude=location.latitude,
        longitude=location.longitude,
        status=location.status,
    )


def restaurant_to_out(restaurant) -> RestaurantOut:
    return RestaurantOut(
        id=restaurant.id,
        name=restaurant.name,
        brand_name=restaurant.brand_name,
        description=restaurant.description,
        phone=restaurant.phone,
        email=restaurant.email,
        status=restaurant.status,
        source=restaurant.source,
        direct2door_enabled=restaurant.direct2door_enabled,
        website=restaurant.website,
        primary_category=restaurant.primary_category,
        price_level=restaurant.price_level,
        rating_avg=restaurant.rating_avg,
        rating_count=restaurant.rating_count,
        owner_name=restaurant.owner_name,
        business_address=restaurant.business_address,
        verification_status=restaurant.verification_status,
        verification_notes=restaurant.verification_notes,
        verified_at=restaurant.verified_at,
        locations=[location_to_out(loc) for loc in restaurant.locations],
        created_at=restaurant.created_at,
    )


def menu_item_to_out(item) -> MenuItemOut:
    return MenuItemOut(
        id=item.id,
        menu_id=item.menu_id,
        name=item.name,
        description=item.description,
        price_cents=item.price_cents,
        category=item.category,
        available=item.available,
        image_url=item.image_url,
        modifiers=[
            ModifierOut(
                id=m.id,
                name=m.name,
                price_delta_cents=m.price_delta_cents,
                required=m.required,
                max_selections=m.max_selections,
            )
            for m in item.modifiers
        ],
    )
