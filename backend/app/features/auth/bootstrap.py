"""First-admin bootstrap.

On startup, if NO users exist and `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`
are set in env, create an admin user (assigned the `admin` role). Idempotent
and safe on every boot — bails the moment any user is found.

This avoids the chicken-and-egg of "you can't manage users without logging in
and you can't log in without a user".
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Config
from app.features.auth import service as auth_service


async def bootstrap_admin_if_empty(session: AsyncSession) -> bool:
    """Create the bootstrap admin if env allows and the user table is empty.

    Returns True if a user was created (logged by the lifespan). Idempotent.
    """
    if await auth_service.any_users_exist(session):
        return False

    email = (Config.BOOTSTRAP_ADMIN_EMAIL or "").strip().lower()
    password = Config.BOOTSTRAP_ADMIN_PASSWORD or ""
    if not email or not password:
        # Nothing to bootstrap — caller can create the first admin another way.
        return False

    await auth_service.create_user(
        session,
        email=email,
        password=password,
        full_name="Bootstrap Admin",
        is_active=True,
        is_superuser=True,
        role_names=["admin"],
    )
    await session.commit()
    return True
