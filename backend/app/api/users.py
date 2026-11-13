"""Current-user profile endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.auth import UpdateProfileRequest, UserOut, user_to_out

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user_to_out(user)


@router.patch("/users/me", response_model=UserOut)
def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.phone is not None:
        user.phone = body.phone
    db.commit()
    db.refresh(user)
    return user_to_out(user)
