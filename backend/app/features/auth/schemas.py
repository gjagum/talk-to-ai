"""Pydantic schemas for the auth/RBAC domain.

Read schemas deliberately OMIT `hashed_password`. Never add it to any schema
that ships to a client.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Permissions & Roles
# ---------------------------------------------------------------------------
class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    permissions: list[PermissionRead] = []


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = None
    permission_ids: list[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None
    permission_ids: list[int] | None = None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    """Admin-only: create a user (no self-registration in v1)."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = None
    role_ids: list[int] = Field(default_factory=list)
    is_active: bool = True
    is_superuser: bool = False


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    role_ids: list[int] | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    roles: list[RoleRead] = []
    # permissions: flattened set derived via service.get_user_permissions
    permissions: list[str] = []


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenWithUser(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserRead"


# Forward-ref resolve (TokenWithUser references UserRead above).
TokenWithUser.model_rebuild()
