import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Vertical slices: each feature module owns its router + services.
from app.features.voice import router as voice_router
from app.features.realtime import router as realtime_router
from app.features.agent import router as agent_router

app = FastAPI(title="Talk to AI")

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

if os.path.isdir("dist"):
    app.frontend("/", directory="dist")
