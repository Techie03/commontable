"""Import all models so Base.metadata covers every table (Alembic + tests)."""

from app.models.drivers import (  # noqa: F401
    DeliveryTask,
    Driver,
    DriverShift,
    DriverVehicle,
)
from app.models.geo import Address, ServiceZone  # noqa: F401
from app.models.identity import Customer, RevokedToken, Role, User, UserRole  # noqa: F401
from app.models.misc import Integration, Notification, SupportTicket  # noqa: F401
from app.models.orders import Order, OrderItem, Rating, StatusEvent  # noqa: F401
from app.models.payments import (  # noqa: F401
    IdempotencyKey,
    LedgerEntry,
    Payment,
    PricingRule,
    Refund,
    Settlement,
)
from app.models.restaurants import (  # noqa: F401
    Menu,
    MenuItem,
    Modifier,
    Restaurant,
    RestaurantLocation,
)
