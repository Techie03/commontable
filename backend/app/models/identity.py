"""Identity models: users, roles, user_roles, customers, revoked_tokens."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.common import utc_datetime, utcnow

# Role names (contract section 1).
ROLE_CUSTOMER = "customer"
ROLE_RESTAURANT_OWNER = "restaurant_owner"
ROLE_RESTAURANT_MANAGER = "restaurant_manager"
ROLE_RESTAURANT_STAFF = "restaurant_staff"
ROLE_DRIVER = "driver"
ROLE_DISPATCHER = "dispatcher"
ROLE_ADMIN = "admin"

ALL_ROLES = [
    ROLE_CUSTOMER,
    ROLE_RESTAURANT_OWNER,
    ROLE_RESTAURANT_MANAGER,
    ROLE_RESTAURANT_STAFF,
    ROLE_DRIVER,
    ROLE_DISPATCHER,
    ROLE_ADMIN,
]

RESTAURANT_ROLES = [ROLE_RESTAURANT_OWNER, ROLE_RESTAURANT_MANAGER, ROLE_RESTAURANT_STAFF]


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)
    updated_at = Column(utc_datetime, nullable=False, default=utcnow, onupdate=utcnow)
    last_login_at = Column(utc_datetime, nullable=True)

    roles = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )
    customer_profile = relationship("Customer", back_populates="user", uselist=False)
    driver_profile = relationship("Driver", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user")

    def role_names(self) -> list[str]:
        return [ur.role.name for ur in self.roles]

    def has_role(self, *names: str, scope_id: int | None = None) -> bool:
        """True if the user holds any of the named roles.

        When scope_id is given, the role grant must be scoped to that
        restaurant (scope_id matches) or be global (scope_id is None).
        Admin is global and bypasses scope checks elsewhere, not here.
        """
        for ur in self.roles:
            if ur.role.name in names:
                if scope_id is None:
                    return True
                if ur.scope_id is None or ur.scope_id == scope_id:
                    return True
        return False

    def restaurant_ids(self, *names: str) -> list[int]:
        """Restaurant ids this user holds any of the named roles for."""
        ids = []
        for ur in self.roles:
            if ur.role.name in names and ur.scope_id is not None:
                ids.append(ur.scope_id)
        return ids


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

    grants = relationship("UserRole", back_populates="role")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "scope_id", name="uq_user_role_scope"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(String(50), nullable=True)  # e.g. "restaurant"
    scope_id = Column(Integer, nullable=True)  # restaurant id for restaurant roles
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    granted_at = Column(utc_datetime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="grants")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    default_address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)
    created_at = Column(utc_datetime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="customer_profile")
    orders = relationship("Order", back_populates="customer")


class RevokedToken(Base):
    """JTI denylist for logged-out / rotated tokens."""

    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    token_type = Column(String(20), nullable=False)  # access | refresh
    revoked_at = Column(utc_datetime, nullable=False, default=utcnow)
    expires_at = Column(utc_datetime, nullable=True)
