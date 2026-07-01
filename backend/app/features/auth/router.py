"""Auth & current-user endpoints.

Public:
  POST /api/auth/login   → returns JWT + minimal user payload

Authenticated (any logged-in user):
  GET  /api/auth/me       → current user with flattened permissions
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Config
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.features.auth import service as auth_service
from app.features.auth.models import User
from app.features.auth.schemas import TokenWithUser, UserLogin, UserRead

router = APIRouter()


def _serialize_user(user: User) -> UserRead:
    """Build the public UserRead (with flattened permissions)."""
    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=user.roles,
        permissions=auth_service.flatten_permissions(user),
    )


@router.post("/login", response_model=TokenWithUser)
async def login(payload: UserLogin, session: AsyncSession = Depends(get_db)):
    """Email + password login. Returns an access token + the user record."""
    user = await auth_service.authenticate(
        session, email=payload.email, password=payload.password
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.id)
    return TokenWithUser(
        access_token=token,
        token_type="bearer",
        user=_serialize_user(user),
    )


@router.get("/me", response_model=UserRead)
async def me(current: User = Depends(get_current_user)):
    """Return the current user with their effective permissions."""
    return _serialize_user(current)
