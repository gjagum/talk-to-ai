from deepgram import DeepgramClient
from app.core.config import Config
import asyncio

dg_client = DeepgramClient(api_key=Config.DEEPGRAM_API_KEY)

async def transcribe_audio_stream(audio_bytes: bytes) -> str:
    """Transcribe audio using Deepgram's prerecorded API."""

    response = await asyncio.to_thread(
        dg_client.listen.v1.media.transcribe_file,
        request=audio_bytes,
        model="nova-2",
        smart_format=True,
        diarize=False
    )

    return response.results.channels[0].alternatives[0].transcript


async def create_live_transcription():
    """Create a Deepgram live transcription connection."""
    return dg_client.listen.v1.connect(
        model="nova-2",
        smart_format=True,
        interim_results=True
    )
