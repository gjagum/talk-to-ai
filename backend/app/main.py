import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Vertical slices: each feature module owns its router + services.
from app.core.database import Base, engine
from app.features.voice import router as voice_router
from app.features.realtime import router as realtime_router
from app.features.agent import router as agent_router
from app.features.booking import router as booking_router

# Import feature models so their tables are registered on Base.metadata before
# create_all runs. (Models register themselves on import.)
import app.features.booking.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (idempotent). Uses create_all for now;
    swap to Alembic migrations when a second persisted domain lands."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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

# Serve the pre-built frontend from the dist/ directory (built by Docker or
# manually via `npm run build`). Falls back to index.html for SPA routes.
if os.path.isdir("dist"):
    app.mount("/", StaticFiles(directory="dist", html=True), name="frontend")
