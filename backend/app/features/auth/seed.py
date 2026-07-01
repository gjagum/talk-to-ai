"""Idempotent seeder for the RBAC catalog: permissions + default roles.

Runs at startup. Permission names follow the "<domain>:<action>" convention so
that adding a new domain (e.g. "audit:") only requires appending a tuple here
and a migration is not needed (this is data, not schema).

Permissions actually granted to default roles:
  - admin  : everything in the catalog
  - viewer : all ":read" permissions only
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import Permission, Role

# ── Permission catalog ─────────────────────────────────────────────────────
# Each tuple: (name, description).
PERMISSIONS: list[tuple[str, str]] = [
    # Agent management
    ("agent:read", "View AI Talking Agents"),
    ("agent:create", "Create new agents"),
    ("agent:update", "Edit existing agents and tool assignments"),
    ("agent:delete", "Delete agents"),
    # Tool management
    ("tool:read", "View Tools"),
    ("tool:create", "Create new tools"),
    ("tool:update", "Edit existing tools"),
    ("tool:delete", "Delete tools"),
    # User & role management
    ("user:read", "View users"),
    ("user:create", "Create users"),
    ("user:update", "Edit users (roles, active, reset password)"),
    ("user:delete", "Delete users"),
    ("role:read", "View roles and permissions"),
    ("role:manage", "Create/edit roles and assign permissions"),
    # System
    ("system:admin", "Administrative access to settings/seeds"),
]

ALL_NAMES = [name for name, _ in PERMISSIONS]
READ_ONLY = [n for n in ALL_NAMES if n.endswith(":read")]


async def seed_if_empty(session: AsyncSession) -> None:
    """Ensure the permission catalog + default roles exist. Idempotent."""
    # Permissions (insert any missing by name).
    existing_perms = {
        p.name: p for p in (await session.execute(select(Permission))).scalars().all()
    }
    new_perms: list[Permission] = []
    for name, desc in PERMISSIONS:
        if name not in existing_perms:
            perm = Permission(name=name, description=desc)
            session.add(perm)
            new_perms.append(perm)
    if new_perms:
        await session.flush()  # populate ids

    all_perms = {p.name: p for p in (
        await session.execute(select(Permission))
    ).scalars().all()}

    # Default roles (upsert two: admin, viewer).
    existing_roles = {
        r.name: r for r in (
            await session.execute(select(Role).options())
        ).scalars().all()
    }

    def _ensure_role(name: str, description: str, perm_names: list[str]) -> Role:
        role = existing_roles.get(name)
        if role is None:
            role = Role(name=name, description=description)
            session.add(role)
            existing_roles[name] = role
        else:
            role.description = description
        role.permissions = [all_perms[n] for n in perm_names if n in all_perms]
        return role

    _ensure_role("admin", "Full administrative access", ALL_NAMES)
    _ensure_role("viewer", "Read-only across the dashboard", READ_ONLY)

    await session.commit()
