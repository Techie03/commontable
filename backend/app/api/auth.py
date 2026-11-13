"""Auth router: register (customer only), login, refresh, logout."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.errors import bad_request, conflict, unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.identity import Customer, RevokedToken, Role, User, UserRole
from app.models.common import utcnow
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    user_to_out,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=user_to_out(user),
    )


def _grant_customer_role(db: Session, user: User) -> None:
    role = db.query(Role).filter(Role.name == "customer").first()
    if role is None:
        role = Role(name="customer", description="Customer")
        db.add(role)
        db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(Customer(user_id=user.id))


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create a customer account. Only the customer role is granted here;
    staff/driver/dispatcher/admin roles are granted by an admin."""
    existing = db.query(User).filter(User.email == body.email).first()
    if existing is not None:
        raise conflict("An account with that email already exists")
    user = User(
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()
    _grant_customer_role(db, user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise unauthorized("Email or password is incorrect")
    if not user.is_active:
        raise unauthorized("This account is inactive")
    user.last_login_at = utcnow()
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


def _revoke_jti(db: Session, payload: dict, token_type: str) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    if db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        return
    expires_at = None
    exp = payload.get("exp")
    if exp:
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    db.add(RevokedToken(jti=jti, token_type=token_type, expires_at=expires_at))


@router.post("/refresh", response_model=AuthResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise unauthorized("Invalid or expired refresh token")
    jti = payload.get("jti")
    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise unauthorized("This refresh token has been revoked")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None or not user.is_active:
        raise unauthorized("Account not found or inactive")
    # Rotate: revoke the presented refresh token, issue a fresh pair.
    _revoke_jti(db, payload, "refresh")
    db.commit()
    return _issue_tokens(user)


@router.post("/logout")
def logout(
    body: LogoutRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the refresh token (jti denylist)."""
    if body is not None and body.refresh_token:
        payload = decode_token(body.refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise bad_request("Invalid refresh token")
        _revoke_jti(db, payload, "refresh")
        db.commit()
    return {"message": "Logged out"}
