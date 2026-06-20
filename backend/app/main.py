from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import voice, realtime, agent

app = FastAPI(title="Voice AI Agent POC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Response"]
)

app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
app.include_router(realtime.router, prefix="/api/realtime", tags=["realtime"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])

app.frontend("/", directory="dist")
