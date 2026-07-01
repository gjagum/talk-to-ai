import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import Config
from app.core.database import AsyncSessionLocal
from app.core.migrations import upgrade_head

# Vertical slices: each feature module owns its router + services.
from app.features.voice import router as voice_router
from app.features.realtime import router as realtime_router
from app.features.agent import router as agent_router
from app.features.booking import router as booking_router
from app.features.menu import router as menu_router
from app.features.menu.seed import seed_if_empty as seed_menu

# Import feature models to ensure SQLAlchemy mappings are loaded.
import app.features.booking.models  # noqa: F401
import app.features.menu.models  # noqa: F401
import app.features.auth.models  # noqa: F401
import app.features.agent_management.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run Alembic migrations (or create_all if USE_CREATE_ALL=true), then
    seed menu items, RBAC permissions/roles, bootstrap admin, and agent tools.

    Migration mode (default, production-safe):
        alembic upgrade head via app.core.migrations.upgrade_head()

    Legacy create_all mode (dev, opt-in):
        Set USE_CREATE_ALL=true in environment.  Useful for throw-away DBs or
        when running without a configured alembic.ini path.
    """
    if Config.USE_CREATE_ALL:
        from app.core.database import Base, engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Created all tables via Base.metadata.create_all")
    else:
        upgrade_head()
        print("Alembic migrations up to date")

    async with AsyncSessionLocal() as session:
        # 1. Seed menu (static catalogue of Burger Barn items).
        inserted = await seed_menu(session)
        if inserted:
            print(f"Seeded {inserted} menu items")

    async with AsyncSessionLocal() as session:
        # 2. Seed RBAC permissions & roles.
        from app.features.auth.seed import seed_if_empty as seed_auth

        await seed_auth(session)
        print("RBAC permissions & roles seeded")

    async with AsyncSessionLocal() as session:
        # 3. Bootstrap admin from env vars (if no users exist yet).
        from app.features.auth.bootstrap import bootstrap_admin_if_empty

        created = await bootstrap_admin_if_empty(session)
        if created:
            print("Bootstrapped admin user")

    async with AsyncSessionLocal() as session:
        # 4. Seed canonical agents + tools.
        from app.features.agent_management.seed import seed_if_empty as seed_agents

        await seed_agents(session)
        print("Canonical agents & tools seeded")

    yield


app = FastAPI(title="Talk to AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Response"]
)

# Mount each feature slice under its own URL prefix.
app.include_router(voice_router.router, prefix="/api/voice", tags=["voice"])
app.include_router(realtime_router.router, prefix="/api/realtime", tags=["realtime"])
app.include_router(agent_router.router, prefix="/api/agent", tags=["agent"])
app.include_router(booking_router.router, prefix="/api/booking", tags=["booking"])
app.include_router(menu_router.router, prefix="/api/menu", tags=["menu"])

# Auth + admin routes (permission-gated dashboard API).
from app.features.auth import router as auth_router
from app.features.agent_management import router as am_router
from app.features.agent_management import public_router as am_public_router

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(am_router.router, prefix="/api/admin", tags=["admin"])
# Public persona read/write for the voice-demo pages (allowlisted to the two
# canonical seeded agents). Mounted at root so the public paths are
# /api/agents/<name>/persona.
app.include_router(am_public_router.router, prefix="/api", tags=["agent-persona"])

# Serve the pre-built frontend from the dist/ directory (built by Docker or
# manually via `npm run build`). Falls back to index.html for SPA routes.
if os.path.isdir("dist"):
    app.mount("/", StaticFiles(directory="dist", html=True), name="frontend")
