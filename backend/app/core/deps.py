"""Auth + RBAC dependencies (spec section 4 permissions matrix).

Every endpoint enforces role + ownership server-side: a customer sees only
their own orders, restaurant staff only their restaurant's data, a driver
only their own offers and deliveries.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.core.errors import forbidden, unauthorized
from app.core.security import decode_token
from app.db.session import get_db
from app.models.identity import (
    RESTAURANT_ROLES,
    ROLE_ADMIN,
    ROLE_DISPATCHER,
    User,
    UserRole,
    RevokedToken,
)
from app.models.orders import Order

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise unauthorized()
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise unauthorized("Invalid or expired access token")
    jti = payload.get("jti")
    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise unauthorized("Token has been revoked")
    user_id = payload.get("sub")
    user = (
        db.query(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .filter(User.id == int(user_id))
        .first()
    )
    if user is None or not user.is_active:
        raise unauthorized("Account not found or inactive")
    return user


def require_roles(*role_names: str):
    """Dependency factory: the caller must hold at least one named role."""

    def _check(user: User = Depends(get_current_user)) -> User:
        if not user.has_role(*role_names):
            raise forbidden("Your account does not have access to this")
        return user

    return _check


def is_admin(user: User) -> bool:
    return user.has_role(ROLE_ADMIN)


def is_dispatcher_or_admin(user: User) -> bool:
    return user.has_role(ROLE_DISPATCHER, ROLE_ADMIN)


def require_restaurant_access(
    restaurant_id: int, user: User, allowed_roles: list[str] | None = None
) -> None:
    """Raise 403 unless the user is admin or holds a restaurant role scoped
    to this restaurant (optionally restricted to allowed_roles)."""
    if is_admin(user):
        return
    roles = allowed_roles or RESTAURANT_ROLES
    if not user.has_role(*roles, scope_id=restaurant_id):
        raise forbidden("You do not have access to this restaurant")


def require_order_access(order: Order, user: User) -> None:
    """Order detail access: owner customer, staff of the restaurant,
    dispatcher, or admin (contract section 3)."""
    if is_admin(user) or user.has_role(ROLE_DISPATCHER):
        return
    if order.customer is not None and order.customer.user_id == user.id:
        return
    if user.has_role(*RESTAURANT_ROLES, scope_id=order.restaurant_id):
        return
    raise forbidden("You do not have access to this order")


def get_driver_profile(user: User, db: Session):
    """Return the caller's driver profile, or raise 403."""
    from app.models.drivers import Driver

    driver = db.query(Driver).filter(Driver.user_id == user.id).first()
    if driver is None:
        raise forbidden("This account is not a driver account")
    return driver
