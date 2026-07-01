"""Shared FastAPI dependencies: current-user resolution + RBAC guards.

These are imported by every protected feature router. They live in `app.core`
(rather than `app.features.auth`) so feature modules don't need a circular
import on auth — `features.auth` is one peer among many.

Usage:
    from app.core.deps import get_current_user, require_permission

    @router.get("/", dependencies=[Depends(require_permission("agent:read"))])
    async def list_agents(...): ...

    @router.get("/me")
    async def me(current: User = Depends(get_current_user)): ...
"""
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import JWTError, decode_token
from app.features.auth.models import User
from app.features.auth import service as auth_service

# `tokenUrl` is theSwagger UI "Authorize" hint; it points at our login route.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the JWT to a User. Raises 401 if invalid/expired/unknown user."""
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise creds_error
        user_id = int(user_id_raw)
    except (JWTError, ValueError, TypeError):
        raise creds_error

    user = await auth_service.get_user(session, user_id)
    if user is None:
        raise creds_error
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


def require_permission(name: str) -> Callable:
    """Build a dependency that allows the call only if the user has `name`.

    `is_superuser` short-circuits — always allowed. Otherwise the user's
    effective permission set (union across all their roles) must contain `name`.
    """

    async def _checker(current: User = Depends(get_current_user)) -> User:
        if current.is_superuser:
            return current
        allowed = set(auth_service.flatten_permissions(current))
        if name not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {name}",
            )
        return current

    _checker.__name__ = f"require_permission_{name.replace(':', '_').replace('-', '_')}"
    return _checker
