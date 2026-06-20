"""Request/response voice pipeline: STT -> LLM -> TTS (HTTP endpoints).

Two provider variants are exposed side-by-side:
  /process  /greeting            -- OpenAI (Whisper + TTS)
  /deepgram/process  /greeting   -- Deepgram (nova-2 + Aura-2)
"""
import urllib.parse

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response

from app.features.voice.services import (
    llm as llm_service,
    stt as stt_service,
    tts as tts_service,
    deepgram_stt as deepgram_stt_service,
    deepgram_tts as deepgram_tts_service,
)

router = APIRouter()


def _audio_response(text: str) -> Response:
    """Wrap a TTS'd response, URL-encoding the transcript in headers."""
    safe_text = urllib.parse.quote(text)
    return Response(
        content=None,  # filled in by caller
        media_type="audio/mpeg",
        headers={"X-Response": safe_text},
    )


async def _run_pipeline(
    *,
    audio: UploadFile | None,
    text: str | None,
    persona: str | None,
    transcribe,
    synthesize,
) -> Response:
    """STT -> LLM -> TTS, returning an audio Response with transcript headers."""
    try:
        # 1. STT
        if text:
            transcribed_text = text
            print(f"User said (Browser Native): {transcribed_text}")
        elif audio:
            audio_bytes = await audio.read()
            transcribed_text = await transcribe(audio_bytes)
            print(f"User said: {transcribed_text}")
        else:
            raise HTTPException(status_code=400, detail="No audio or text provided")

        # 2. LLM
        ai_response = await llm_service.generate_response(transcribed_text, persona=persona)
        print(f"AI responds: {ai_response}")

        # 3. TTS
        audio_bytes = await synthesize(ai_response)

        safe_transcript = urllib.parse.quote(transcribed_text)
        safe_response = urllib.parse.quote(ai_response)

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "X-Transcript": safe_transcript,
                "X-Response": safe_response,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_greeting(*, persona: str | None, synthesize) -> Response:
    try:
        greeting_text = await llm_service.generate_greeting(persona=persona)
        audio_bytes = await synthesize(greeting_text)
        safe_response = urllib.parse.quote(greeting_text)

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"X-Response": safe_response},
        )
    except Exception as e:
        print(f"Error generating greeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- OpenAI (Whisper + TTS) -------------------------------------------------
@router.post("/process")
async def process_voice(
    audio: UploadFile = File(None),
    text: str = Form(None),
    persona: str = Form(None),
):
    return await _run_pipeline(
        audio=audio, text=text, persona=persona,
        transcribe=stt_service.transcribe_audio,
        synthesize=tts_service.synthesize_speech,
    )


@router.post("/greeting")
async def get_greeting(persona: str = Form(None)):
    return await _run_greeting(persona=persona, synthesize=tts_service.synthesize_speech)


# --- Deepgram (nova-2 + Aura-2) --------------------------------------------
@router.post("/deepgram/process")
async def process_voice_deepgram(
    audio: UploadFile = File(None),
    text: str = Form(None),
    persona: str = Form(None),
):
    return await _run_pipeline(
        audio=audio, text=text, persona=persona,
        transcribe=deepgram_stt_service.transcribe_audio_stream,
        synthesize=deepgram_tts_service.synthesize_speech,
    )


@router.post("/deepgram/greeting")
async def get_greeting_deepgram(persona: str = Form(None)):
    return await _run_greeting(persona=persona, synthesize=deepgram_tts_service.synthesize_speech)


@router.get("/health")
async def health_check():
    return {"status": "healthy"}
