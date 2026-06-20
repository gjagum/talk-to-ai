from deepgram import DeepgramClient
from app.config import Config
import asyncio

dg_client = DeepgramClient(api_key=Config.DEEPGRAM_API_KEY)

async def synthesize_speech(text: str) -> bytes:
    """Synthesize speech using Deepgram's TTS API."""
    audio_chunks = await asyncio.to_thread(
        dg_client.speak.v1.audio.generate,
        text=text,
        model="aura-2-enth",
        encoding="mp3",
        sample_rate=24000
    )
    
    return b"".join(audio_chunks)