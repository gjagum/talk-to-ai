"""Auth/RBAC business logic — async functions taking an AsyncSession.

Matches the menu/booking service pattern: pure async functions, explicit
commits handled by the caller (router or seeder) where the session is owned.
"""
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.features.auth.models import Permission, Role, User


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def authenticate(
    session: AsyncSession, *, email: str, password: str
) -> User | None:
    """Return the User if credentials match, else None.

    Eager-loads roles (+ their permissions via selectin on Role) so the caller
    can flatten the permission set without an extra round-trip.
    """
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ---------------------------------------------------------------------------
# User lookups
# ---------------------------------------------------------------------------
async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = (
        select(User)
        .where(User.email == email)
        .options(selectinload(User.roles))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id).options(selectinload(User.roles))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_users(session: AsyncSession) -> list[User]:
    stmt = select(User).order_by(User.id).options(selectinload(User.roles))
    return list((await session.execute(stmt)).scalars().all())


async def any_users_exist(session: AsyncSession) -> bool:
    stmt = select(User.id).limit(1)
    return (await session.execute(stmt)).first() is not None


def flatten_permissions(user: User) -> list[str]:
    """Return the union of permission names across all the user's roles."""
    names: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            names.add(perm.name)
    return sorted(names)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------
async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
    is_active: bool = True,
    is_superuser: bool = False,
    role_names: Iterable[str] = (),
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_active=is_active,
        is_superuser=is_superuser,
    )
    if role_names:
        roles = await get_roles_by_names(session, list(role_names))
        user.roles = roles
    session.add(user)
    await session.flush()
    return user


# ---------------------------------------------------------------------------
# Roles / permissions helpers
# ---------------------------------------------------------------------------
async def get_roles_by_names(session: AsyncSession, names: list[str]) -> list[Role]:
    if not names:
        return []
    stmt = select(Role).where(Role.name.in_(names))
    return list((await session.execute(stmt)).scalars().all())


async def get_role_by_name(session: AsyncSession, name: str) -> Role | None:
    return (await session.execute(select(Role).where(Role.name == name))).scalar_one_or_none()


async def get_permissions_by_names(
    session: AsyncSession, names: list[str]
) -> list[Permission]:
    if not names:
        return []
    stmt = select(Permission).where(Permission.name.in_(names))
    return list((await session.execute(stmt)).scalars().all())
