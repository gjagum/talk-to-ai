"""WebSocket relay between the browser and Deepgram's Voice Agent API.

Deepgram sends/receives raw binary PCM audio frames interleaved with JSON text
events on the same connection. This relay forwards text frames as text and
binary frames as bytes, preserving that interleaved stream.
"""
import asyncio
import json

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from app.core.config import Config
from app.features.agent.settings import DEFAULT_PERSONA, build_settings

DEEPGRAM_AGENT_WS_URL = "wss://agent.deepgram.com/v1/agent/converse"


async def _wait_for_welcome(deepgram_ws) -> None:
    """Read messages until Welcome arrives. Required before Settings."""
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
        while True:
            msg = await client_ws.receive()
            if "text" in msg and msg["text"] is not None:
                payload = json.loads(msg["text"])
                if payload.get("type") == "Init":
                    persona = payload.get("persona") or ""
                    if persona:
                        return persona
                    break  # empty persona → fall through to default
    except WebSocketDisconnect:
        raise
    except Exception as e:
        print(f"Error reading Init/persona from client: {e}")

    return DEFAULT_PERSONA


async def _pump_browser_to_deepgram(client_ws: WebSocket, deepgram_ws):
    """Browser -> Deepgram. Binary = audio, text = JSON control messages."""
    try:
        while True:
            msg = await client_ws.receive()
            if "bytes" in msg and msg["bytes"] is not None:
                # Raw PCM16 audio from the microphone.
                await deepgram_ws.send(msg["bytes"])
            elif "text" in msg and msg["text"] is not None:
                # JSON control message (e.g. UpdatePrompt, InjectUserMessage).
                await deepgram_ws.send(msg["text"])
    except WebSocketDisconnect:
        print("Client disconnected from agent relay.")
    except Exception as e:
        print(f"Error in browser→deepgram pump: {e}")


async def _pump_deepgram_to_browser(deepgram_ws, client_ws: WebSocket):
    """Deepgram -> Browser. Forward JSON events as text, binary audio as bytes."""
    try:
        async for raw in deepgram_ws:
            if isinstance(raw, bytes):
                await client_ws.send_bytes(raw)
            else:
                await client_ws.send_text(raw)
    except Exception as e:
        print(f"Error in deepgram→browser pump: {e}")


async def relay(client_ws: WebSocket) -> None:
    """Run the full Deepgram Voice Agent session for one connected browser."""
    # Persona arrives as the first client message (too large for the URL).
    persona = await _read_persona_from_client(client_ws)

    headers = {"Authorization": f"Token {Config.DEEPGRAM_API_KEY}"}

    try:
        async with websockets.connect(DEEPGRAM_AGENT_WS_URL, additional_headers=headers) as deepgram_ws:
            print("Connected to Deepgram Voice Agent API.")

            # Handshake: Welcome -> Settings -> SettingsApplied
            await _wait_for_welcome(deepgram_ws)
            await _send_settings_and_wait(deepgram_ws, build_settings(persona))

            # Audio pumps run only after the handshake completes.
            task_client = asyncio.create_task(_pump_browser_to_deepgram(client_ws, deepgram_ws))
            task_deepgram = asyncio.create_task(_pump_deepgram_to_browser(deepgram_ws, client_ws))

            done, pending = await asyncio.wait(
                [task_client, task_deepgram],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except Exception as e:
        print(f"Error connecting to Deepgram Voice Agent API: {e}")
        try:
            await client_ws.send_text(
                json.dumps({"type": "Error", "description": str(e), "code": "relay_error"})
            )
        except Exception:
            pass
