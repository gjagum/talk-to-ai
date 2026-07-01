import os
from dotenv import load_dotenv

# `.env` is authoritative for local dev — override any stale or malformed
# DATABASE_URL that may be lingering in the OS environment. Without this a
# stray system-level env var would silently shadow the corrected .env value.
load_dotenv(override=True)

class Config:
    # ── Existing ───────────────────────────────────────────────────────────
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    MAX_CONVERSATION_HISTORY = 10

    # ── Auth (JWT) ─────────────────────────────────────────────────────────
    # A dev fallback keeps `python -m app.main` runnable without setup; prod
    # MUST override via env. HS256 is fine for a single-server demo.
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-in-production")
    JWT_ALG = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

    # ── First-admin bootstrap ──────────────────────────────────────────────
    # On startup, if no users exist, an admin is created from these env vars
    # so the dashboard is reachable on a fresh DB. Leave unset to skip.
    BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
    BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")

    # ── Migrations ─────────────────────────────────────────────────────────
    # When True, lifespan uses Base.metadata.create_all (fast local dev). When
    # False (default, recommended) lifespan runs `alembic upgrade head`.
    USE_CREATE_ALL = os.getenv("USE_CREATE_ALL", "false").lower() == "true"
