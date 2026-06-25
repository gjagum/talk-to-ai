"""Settings builder for Deepgram Voice Agent (STT -> LLM -> TTS pipeline).

Configures the single managed WebSocket at wss://agent.deepgram.com/v1/agent/converse
to use:
  - audio:    linear16 PCM @ 24kHz in both directions (matches browser).
  - listen:   Deepgram nova-3 with smart formatting.
  - think:    BYO OpenAI gpt-4o-mini (endpoint + auth header → bills caller's
              OpenAI account, not Deepgram's).
  - speak:    Deepgram aura-asteria-en, highest-quality English female voice.
"""
from app.core.config import Config

# One-time greeting the agent speaks when the caller connects.
DEFAULT_GREETING = "Hi! You've reached Kinetic Innovative Staffing. This is Ryan. How can I help you today?"

DEFAULT_PERSONA = (
    "You are Ryan, a friendly AI receptionist for Kinetic Innovative Staffing. "
    "Be warm, concise, and helpful."
)


def build_settings(persona: str) -> dict:
    """Build the Settings message sent after the Welcome handshake."""
    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": 24000},
            "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
        },
        "agent": {
            "listen": {
                "provider": {
                    "type": "deepgram",
                    "model": "nova-3",
                    "smart_format": True,
                    "language": "en",
                }
            },
            "think": {
                "provider": {"type": "open_ai", "model": "gpt-4o-mini", "temperature": 0.7},
                "endpoint": {
                    "url": "https://api.openai.com/v1/chat/completions",
                    "headers": {"authorization": f"Bearer {Config.OPENAI_API_KEY}"},
                },
                "prompt": persona,
            },
            "speak": {
                "provider": {"type": "deepgram", "model": "aura-asteria-en"},
            },
            "greeting": DEFAULT_GREETING,
        },
    }
