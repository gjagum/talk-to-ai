from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from app.services import stt_service, llm_service, tts_service
from app.services import deepgram_stt_service, deepgram_tts_service
import urllib.parse

router = APIRouter()

# OpenAI (Whisper + TTS) endpoints
@router.post("/process")
async def process_voice(audio: UploadFile = File(None), text: str = Form(None), persona: str = Form(None)):
    try:
        transcribed_text = ""
        
        # 1. STT
        if text:
            transcribed_text = text
            print(f"User said (Browser Native): {transcribed_text}")
        elif audio:
            audio_bytes = await audio.read()
            transcribed_text = await stt_service.transcribe_audio(audio_bytes)
            print(f"User said (Whisper): {transcribed_text}")
        else:
            raise HTTPException(status_code=400, detail="No audio or text provided")
        
        # 2. LLM
        ai_response = await llm_service.generate_response(transcribed_text, persona=persona)
        print(f"AI responds: {ai_response}")
        
        # 3. TTS
        audio_response = await tts_service.synthesize_speech(ai_response)
        
        safe_transcript = urllib.parse.quote(transcribed_text)
        safe_response = urllib.parse.quote(ai_response)
        
        return Response(
            content=audio_response,
            media_type="audio/mpeg",
            headers={
                "X-Transcript": safe_transcript,
                "X-Response": safe_response
            }
        )
    
    except Exception as e:
        print(f"Error processing voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/greeting")
async def get_greeting(persona: str = Form(None)):
    try:
        greeting_text = await llm_service.generate_greeting(persona=persona)
        
        # 2. Synthesize
        audio_response = await tts_service.synthesize_speech(greeting_text)
        safe_response = urllib.parse.quote(greeting_text)
        
        return Response(
            content=audio_response,
            media_type="audio/mpeg",
            headers={
                "X-Response": safe_response
            }
        )
    except Exception as e:
        print(f"Error generating greeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Deepgram (Real-time STT + TTS) endpoints
@router.post("/deepgram/process")
async def process_voice_deepgram(audio: UploadFile = File(None), text: str = Form(None), persona: str = Form(None)):
    try:
        transcribed_text = ""
        
        # 1. STT - Deepgram
        if text:
            transcribed_text = text
            print(f"User said (Browser Native): {transcribed_text}")
        elif audio:
            audio_bytes = await audio.read()
            transcribed_text = await deepgram_stt_service.transcribe_audio_stream(audio_bytes)
            print(f"User said (Deepgram): {transcribed_text}")
        else:
            raise HTTPException(status_code=400, detail="No audio or text provided")
        
        # 2. LLM
        ai_response = await llm_service.generate_response(transcribed_text, persona=persona)
        print(f"AI responds: {ai_response}")
        
        # 3. TTS - Deepgram
        audio_response = await deepgram_tts_service.synthesize_speech(ai_response)
        
        safe_transcript = urllib.parse.quote(transcribed_text)
        safe_response = urllib.parse.quote(ai_response)
        
        return Response(
            content=audio_response,
            media_type="audio/mpeg",
            headers={
                "X-Transcript": safe_transcript,
                "X-Response": safe_response
            }
        )
    
    except Exception as e:
        print(f"Error processing voice with Deepgram: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deepgram/greeting")
async def get_greeting_deepgram(persona: str = Form(None)):
    try:
        greeting_text = await llm_service.generate_greeting(persona=persona)
        
        # Synthesize with Deepgram
        audio_response = await deepgram_tts_service.synthesize_speech(greeting_text)
        safe_response = urllib.parse.quote(greeting_text)
        
        return Response(
            content=audio_response,
            media_type="audio/mpeg",
            headers={
                "X-Response": safe_response
            }
        )
    except Exception as e:
        print(f"Error generating greeting with Deepgram: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "healthy"}
