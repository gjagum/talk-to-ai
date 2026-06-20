from openai import OpenAI
from app.config import Config

client = OpenAI(api_key=Config.OPENAI_API_KEY)

async def synthesize_speech(text: str) -> bytes:
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text
    )
    return response.content
