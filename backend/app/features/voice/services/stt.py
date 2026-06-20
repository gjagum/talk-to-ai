from openai import OpenAI
from app.core.config import Config
import io

client = OpenAI(api_key=Config.OPENAI_API_KEY)

async def transcribe_audio(audio_bytes: bytes) -> str:
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.webm"

    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )
    return response.text
