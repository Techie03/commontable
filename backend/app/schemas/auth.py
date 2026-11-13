"""Auth and user schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    # Plain str, not EmailStr: email-validator rejects the .local demo
    # domain the contract specifies for demo users.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    # Self-service role: customer, restaurant_owner, or driver.
    # Dispatcher, admin, and the other restaurant staff roles are granted
    # by an admin, never self-assigned.
    role: str = "customer"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class RoleOut(BaseModel):
    name: str
    scope_type: str | None = None
    scope_id: int | None = None


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    phone: str | None = None
    roles: list[RoleOut] = []
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)


def user_to_out(user) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        roles=[
            RoleOut(name=ur.role.name, scope_type=ur.scope_type, scope_id=ur.scope_id)
            for ur in user.roles
        ],
        created_at=user.created_at,
    )
