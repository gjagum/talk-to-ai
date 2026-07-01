"""RBAC domain models: User, Role, Permission (with M:N associations).

Design notes:
  - Permissions are the atomic unit of authorization. A dependency like
    `require_permission("agent:create")` checks the user's effective permission
    set, regardless of how they got it (through one or more roles).
  - Roles are bundles of permissions (e.g. "admin", "viewer"). Many-to-many.
  - Users get permissions transitively through their roles. `is_superuser`
    short-circuits everything for a break-glass account.
  - `email` is unique and is the login identity.

Registered on Base.metadata at import time; `app.main` (or `alembic/env.py`)
imports this module before running migrations.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Association tables (declared as Table for clarity as pure join tables) ──
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Convention: "<domain>:<action>" e.g. "agent:create", "user:read"
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permissions, lazy="selectin"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    # bcrypt hashes; never returned by any schema (Read models use Read schemas
    # that omit this field).
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Break-glass flag: superusers bypass all permission checks.
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles, lazy="selectin", back_populates="users"
    )


# back-populates on Role.users (declared after User exists)
Role.users = relationship("User", secondary=user_roles, back_populates="roles")
