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

FAREWELL_DELAY_SECONDS = 1.2
DEAD_AIR_TIMEOUT = 8.0  # seconds of silence before auto-ending call

_FAREWELL_WORDS = [
    "goodbye", "bye", "bye bye", "farewell",
    "have a great day", "have a good day", "have a nice day", "have a wonderful day",
    "have a great evening", "have a good evening", "have a great one",
    "have a good one",
    "thanks for calling", "thank you for calling",
    "take care",
    "good night", "good evening", "good day",
    "talk soon", "talk to you soon", "talk later", "talk to you later",
]


def _is_farewell(content: str) -> bool:
    """True if *content* ends with a recognised farewell phrase."""
    cleaned = content.strip().rstrip('.!?,;: \t\n').lower()
    for word in _FAREWELL_WORDS:
        if cleaned.endswith(word):
            return True
    return False


async def _send_end_call(client_ws: WebSocket, reason: str) -> None:
    """Signal the browser to disconnect, after a short delay for TTS to finish."""
    print(f"EndCall triggered (reason={reason}) — waiting {FAREWELL_DELAY_SECONDS}s for TTS")
    await asyncio.sleep(FAREWELL_DELAY_SECONDS)
    try:
        await client_ws.send_text(json.dumps({"type": "EndCall", "reason": reason}))
    except Exception:
        pass


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
    """Deepgram -> Browser. Forward JSON events as text, binary audio as bytes.

    End-call triggers (any one of these fires once, then the pump drains):
      1. FunctionCallRequest for gja_end_call (primary — LLM tool calling).
      2. Assistant ConversationText ending in a farewell phrase (fallback).
      3. Dead air: AgentAudioDone followed by >DEAD_AIR_TIMEOUT s of silence.
    """
    ended = asyncio.Event()
    dead_air_task = None

    def _cancel_dead_air():
        nonlocal dead_air_task
        if dead_air_task:
            dead_air_task.cancel()
            dead_air_task = None

    def _start_dead_air():
        nonlocal dead_air_task
        _cancel_dead_air()

        async def _timeout():
            try:
                await asyncio.sleep(DEAD_AIR_TIMEOUT)
                if not ended.is_set():
                    print("Dead air timeout — ending call")
                    ended.set()
                    await _send_end_call(client_ws, "dead_air")
            except asyncio.CancelledError:
                pass

        dead_air_task = asyncio.create_task(_timeout())

    try:
        async for raw in deepgram_ws:
            if isinstance(raw, bytes):
                await client_ws.send_bytes(raw)
                continue

            if ended.is_set():
                continue

            try:
                msg = json.loads(raw)
            except (TypeError, ValueError):
                await client_ws.send_text(raw)
                continue

            dg_type = msg.get("type", "")

            # ── user activity resets the dead-air clock ──
            if dg_type == "UserStartedSpeaking" or (
                dg_type == "ConversationText" and msg.get("role") == "user"
            ):
                _cancel_dead_air()

            # ── trigger 1: LLM tool calling ──
            if dg_type == "FunctionCallRequest":
                print(f"DG→relay: FunctionCallRequest {json.dumps(msg)}")
                await _handle_function_call(deepgram_ws, client_ws, msg, ended)
                continue

            # ── trigger 2: farewell phrase in assistant text ──
            if dg_type == "ConversationText" and msg.get("role") == "assistant":
                content = msg.get("content", "")
                if _is_farewell(content):
                    print(f"Farewell detected in assistant text: {content[:80]}")
                    ended.set()
                    _cancel_dead_air()
                    asyncio.create_task(_send_end_call(client_ws, "goodbye"))
                    await client_ws.send_text(raw)
                    continue

            # ── trigger 3: dead-air timer starts after agent finishes ──
            if dg_type == "AgentAudioDone":
                _start_dead_air()

            # Debug: log non-verbose Deepgram events.
            if dg_type not in ("UserStartedSpeaking", "AgentStartedSpeaking", "AgentThinking"):
                print(f"DG→browser: {dg_type}")

            await client_ws.send_text(raw)
    except Exception as e:
        print(f"Error in deepgram→browser pump: {e}")
    finally:
        _cancel_dead_air()


async def _handle_function_call(deepgram_ws, client_ws: WebSocket, msg: dict, ended: asyncio.Event) -> None:
    """Dispatch a FunctionCallRequest to the correct tool and reply."""
    functions = msg.get("functions", [])
    for func in functions:
        func_id = func.get("id", "")
        func_name = func.get("name", "")

        try:
            arguments = json.loads(func.get("arguments", "{}"))
        except (TypeError, ValueError):
            arguments = {}

        if func_name == "gja_end_call":
            reason = arguments.get("reason", "goodbye")
            print(f"gja_end_call invoked (reason={reason})")

            response_content = json.dumps({"status": "ok", "reason": reason})
            await deepgram_ws.send(json.dumps({
                "type": "FunctionCallResponse",
                "id": func_id,
                "name": func_name,
                "content": response_content,
            }))

            ended.set()
            asyncio.create_task(_send_end_call(client_ws, reason))
        else:
            print(f"Unknown function call: {func_name}")


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
