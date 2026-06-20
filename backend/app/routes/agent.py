"""Deepgram Voice Agent WebSocket relay.

Provides a managed STT (Deepgram) → LLM (OpenAI gpt-4o-mini) → TTS (Deepgram
Aura-2) pipeline through a single WebSocket connection by proxying between the
browser and Deepgram's Voice Agent API at wss://agent.deepgram.com/v1/agent/converse.

Unlike the OpenAI Realtime relay (which uses base64-in-JSON), Deepgram sends
and receives raw binary PCM audio frames interleaved with JSON text events on
the same connection. This relay preserves that: text frames forward as text,
binary frames forward as bytes.
"""
import asyncio
import json
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import Config

router = APIRouter()

DEEPGRAM_AGENT_WS_URL = "wss://agent.deepgram.com/v1/agent/converse"

# One-time greeting the agent speaks when the caller connects.
DEFAULT_GREETING = "Hi! You've reached Kinetic Innovative Staffing. This is Ryan. How can I help you today?"


def build_settings(persona: str) -> dict:
    """Build the Settings message sent to Deepgram after the Welcome handshake.

    Configures:
      - Audio: linear16 PCM at 24kHz in both directions (matches the browser).
      - listen: Deepgram nova-3 STT with smart formatting for readable transcripts.
      - think:  BYO OpenAI gpt-4o-mini LLM using the caller's own OpenAI key.
                (Deepgram manages the request; we supply the endpoint so calls
                 bill to the user's OpenAI account rather than Deepgram's.)
      - speak:  Deepgram aura-2-thalia-en TTS, a natural English female voice.
    """
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
                "provider": {"type": "deepgram", "model": "aura-2-thalia-en"},
            },
            "greeting": DEFAULT_GREETING,
        },
    }


async def _wait_for_welcome(deepgram_ws) -> None:
    """Read messages until Welcome arrives. Deepgram requires this before Settings."""
    async for raw in deepgram_ws:
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            continue  # ignore unexpected binary frame
        if msg.get("type") == "Welcome":
            return
        if msg.get("type") == "Error":
            raise RuntimeError(f"Deepgram error during handshake: {msg.get('description')}")


async def _send_settings_and_wait(deepgram_ws, settings: dict) -> None:
    """Send Settings and wait for SettingsApplied before audio begins."""
    await deepgram_ws.send(json.dumps(settings))
    async for raw in deepgram_ws:
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if msg.get("type") == "SettingsApplied":
            return
        if msg.get("type") == "Error":
            raise RuntimeError(f"Deepgram rejected Settings: {msg.get('description')}")


async def _read_persona_from_client(client_ws: WebSocket) -> str:
    """Wait for the browser's first text message containing the persona.

    The persona (system prompt) is too large to send via URL query string —
    it can easily exceed the WebSocket handshake's request-line size limit. So
    the browser sends it as the first JSON text frame after the socket opens.
    Expected message: {"type": "Init", "persona": "<system prompt>"}
    """
    try:
        # Drain any binary frames (early mic audio) until we see the Init text frame.
        while True:
            msg = await client_ws.receive()
            if "text" in msg and msg["text"] is not None:
                payload = json.loads(msg["text"])
                if payload.get("type") == "Init":
                    persona = payload.get("persona") or ""
                    if persona:
                        return persona
                    break  # fall through to default
    except WebSocketDisconnect:
        raise
    except Exception as e:
        print(f"Error reading Init/persona from client: {e}")

    return (
        "You are Ryan, a friendly AI receptionist for Kinetic Innovative Staffing. "
        "Be warm, concise, and helpful."
    )


async def receive_from_browser(client_ws: WebSocket, deepgram_ws):
    """Browser → Deepgram. Binary frames are audio, text frames are JSON control messages."""
    try:
        while True:
            msg = await client_ws.receive()
            if "bytes" in msg and msg["bytes"] is not None:
                # Raw PCM16 audio from the microphone.
                await deepgram_ws.send(msg["bytes"])
            elif "text" in msg and msg["text"] is not None:
                # JSON control message from the client (e.g. UpdatePrompt, InjectUserMessage).
                await deepgram_ws.send(msg["text"])
    except WebSocketDisconnect:
        print("Client disconnected from agent relay.")
    except Exception as e:
        print(f"Error in browser→deepgram pump: {e}")


async def receive_from_deepgram(deepgram_ws, client_ws: WebSocket):
    """Deepgram → Browser. Forward JSON events as text, binary audio as bytes."""
    try:
        async for raw in deepgram_ws:
            if isinstance(raw, bytes):
                await client_ws.send_bytes(raw)
            else:
                await client_ws.send_text(raw)
    except Exception as e:
        print(f"Error in deepgram→browser pump: {e}")


@router.websocket("/ws")
async def agent_voice(websocket: WebSocket):
    """Relay between the browser and Deepgram's Voice Agent WebSocket.

    Query params:
      persona: (optional) override the system prompt. Defaults to a simple
               receptionist persona passed in from the frontend.
    """
    await websocket.accept()

    # Persona is delivered as the first client message instead of via the URL
    # (it's often >8KB once URL-encoded, which exceeds WS handshake limits).
    persona = await _read_persona_from_client(websocket)

    headers = {"Authorization": f"Token {Config.DEEPGRAM_API_KEY}"}

    try:
        async with websockets.connect(DEEPGRAM_AGENT_WS_URL, additional_headers=headers) as deepgram_ws:
            print("Connected to Deepgram Voice Agent API.")

            # Handshake: Welcome → Settings → SettingsApplied
            await _wait_for_welcome(deepgram_ws)
            await _send_settings_and_wait(deepgram_ws, build_settings(persona))

            # Both pumps active only after the handshake completes.
            task_client = asyncio.create_task(receive_from_browser(websocket, deepgram_ws))
            task_deepgram = asyncio.create_task(receive_from_deepgram(deepgram_ws, websocket))

            done, pending = await asyncio.wait(
                [task_client, task_deepgram],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        print(f"Error connecting to Deepgram Voice Agent API: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "Error", "description": str(e), "code": "relay_error"}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
