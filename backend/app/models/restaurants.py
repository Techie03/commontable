"""Restaurant, location, menu, item, and modifier models."""

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.common import utc_datetime, utcnow

# Restaurant status (contract section 7). Only "active" is orderable and
# listed as serving; "demo" is internal test data, invisible publicly;
# "prospect" restaurants are census data, unclaimed, never orderable,
# and never presented as partners; "pending" restaurants registered and
# await approval — visible in the coming-soon directory, never orderable.
STATUS_PROSPECT = "prospect"
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"
STATUS_DEMO = "demo"

# Verification status (contract section 7). A restaurant may only be
# approved (go live, take orders) after an admin verifies it is a real
# operating business: owner identity, business phone, and business
# address collected at signup and checked against a public listing or
# website before approval. Unverified restaurants can never take orders
# or receive money.
VERIFICATION_UNVERIFIED = "unverified"
VERIFICATION_VERIFIED = "verified"

RESTAURANT_STATUSES = [
    STATUS_PROSPECT,
    STATUS_PENDING,
    STATUS_ACTIVE,
    STATUS_SUSPENDED,
    STATUS_DEMO,
]

# Sources for the source column.
SOURCE_CENSUS = "census"
SOURCE_SEED = "seed"
SOURCE_MANUAL = "manual"

# Statuses a customer may ever see or order from. Demo restaurants are
# internal test fixtures: staff scoped to one can still open its
# dashboard and menu (see the auth-aware gates in api/restaurants.py),
# but customers never see them in lists or menus.
PUBLIC_STATUSES = [STATUS_ACTIVE]

# Statuses an order may be placed against. Demo is orderable only via
# direct API calls (test tooling); it is never listed, so customers
# cannot reach it. Prospects are never orderable.
ORDERABLE_STATUSES = [STATUS_ACTIVE, STATUS_DEMO]


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    brand_name = Column(String(255), nullable=True)
    description = Column(String(1000), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default=STATUS_PENDING, index=True)
    direct2door_enabled = Column(Boolean, nullable=False, default=False)
    onboarding_approved_at = Column(utc_datetime, nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)
    updated_at = Column(utc_datetime, nullable=False, default=utcnow, onupdate=utcnow)

    # Census fields (contract section 7). place_id is the census upsert key.
    place_id = Column(String(255), unique=True, nullable=True, index=True)
    source = Column(String(20), nullable=False, default=SOURCE_MANUAL)
    primary_category = Column(String(255), nullable=True)
    price_level = Column(Integer, nullable=True)
    rating_avg = Column(Float, nullable=True)
    rating_count = Column(Integer, nullable=True)
    maps_search_url = Column(String(1000), nullable=True)
    website = Column(String(1000), nullable=True)

    # Verification evidence, collected at signup and checked by an admin
    # before approval. Census/seed rows have none (never approved).
    owner_name = Column(String(255), nullable=True)
    business_address = Column(String(500), nullable=True)
    verification_status = Column(
        String(20), nullable=False, default=VERIFICATION_UNVERIFIED
    )
    verification_notes = Column(String(2000), nullable=True)
    verified_at = Column(utc_datetime, nullable=True)

    locations = relationship("RestaurantLocation", back_populates="restaurant", cascade="all, delete-orphan")
    menus = relationship("Menu", back_populates="restaurant", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="restaurant")


class RestaurantLocation(Base):
    __tablename__ = "restaurant_locations"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False)
    hours_json = Column(JSON, nullable=True)
    service_zone_ids = Column(JSON, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="active")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    restaurant = relationship("Restaurant", back_populates="locations")
    address = relationship("Address")


class Menu(Base):
    __tablename__ = "menus"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    active = Column(Boolean, nullable=False, default=True)

    restaurant = relationship("Restaurant", back_populates="menus")
    items = relationship("MenuItem", back_populates="menu", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True)
    menu_id = Column(Integer, ForeignKey("menus.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    # Agreed direct menu price, integer cents.
    price_cents = Column(Integer, nullable=False)
    category = Column(String(100), nullable=True)
    available = Column(Boolean, nullable=False, default=True)
    image_url = Column(String(1000), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)
    updated_at = Column(utc_datetime, nullable=False, default=utcnow, onupdate=utcnow)

    menu = relationship("Menu", back_populates="items")
    modifiers = relationship("Modifier", back_populates="menu_item", cascade="all, delete-orphan")


class Modifier(Base):
    __tablename__ = "modifiers"

    id = Column(Integer, primary_key=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    price_delta_cents = Column(Integer, nullable=False, default=0)
    required = Column(Boolean, nullable=False, default=False)
    max_selections = Column(Integer, nullable=True)

    menu_item = relationship("MenuItem", back_populates="modifiers")
