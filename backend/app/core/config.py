import os
from dotenv import load_dotenv

# `.env` is authoritative for local dev — override any stale or malformed
# DATABASE_URL that may be lingering in the OS environment. Without this a
# stray system-level env var would silently shadow the corrected .env value.
load_dotenv(override=True)

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    MAX_CONVERSATION_HISTORY = 10
