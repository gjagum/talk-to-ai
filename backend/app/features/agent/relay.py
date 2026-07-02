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
from app.core.database import AsyncSessionLocal
from app.features.agent import settings as legacy
from app.features.agent_management import service as am_service
from app.features.agent_management.models import Agent
from app.features.agent_management.handlers import (
    ToolCallContext,
    get_handler,
)

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


async def _read_init_from_client(client_ws: WebSocket) -> tuple[str, str, int | None, str | None]:
    """Wait for the browser's first text message containing agent selection.

    The persona (system prompt) is too large to send via URL query string —
    it can easily exceed the WebSocket handshake's request-line size limit. So
    the browser sends it as the first JSON text frame after the socket opens.

    New (data-driven) Init shape:
      {"type":"Init", "agent_id": 3}
      {"type":"Init", "agent_name": "drive_thru"}
    Legacy shape (still supported for backward-compat):
      {"type":"Init", "persona": "<sys prompt>", "mode": "receptionist|drive_thru"}

    Returns (persona_or_blank, legacy_mode, agent_id, agent_name).
    The caller resolves these in priority order: agent_id > agent_name >
    legacy mode -> seeded Agent.
    """
    mode = "receptionist"
    persona = ""
    agent_id: int | None = None
    agent_name: str | None = None

    try:
        while True:
            msg = await client_ws.receive()
            if "text" in msg and msg["text"] is not None:
                payload = json.loads(msg["text"])
                if payload.get("type") == "Init":
                    persona = payload.get("persona") or ""
                    mode = (payload.get("mode") or "receptionist").strip()
                    if "agent_id" in payload and payload["agent_id"] is not None:
                        try:
                            agent_id = int(payload["agent_id"])
                        except (TypeError, ValueError):
                            agent_id = None
                    raw_name = payload.get("agent_name")
                    if raw_name:
                        agent_name = str(raw_name).strip()
                    return persona, mode, agent_id, agent_name
    except WebSocketDisconnect:
        raise
    except Exception as e:
        print(f"Error reading Init from client: {e}")

    return persona, mode, agent_id, agent_name


async def _resolve_agent(
    persona: str, mode: str, agent_id: int | None, agent_name: str | None
) -> Agent | None:
    """Pick the Agent row to drive the call.

    Priority: explicit id > explicit name > legacy `mode` (mapped to a seeded
    Agent name) > None (caller falls back to legacy constants).
    """
    async with AsyncSessionLocal() as session:
        if agent_id is not None:
            agent = await am_service.get_agent(session, agent_id)
            if agent and agent.is_active:
                return agent
        if agent_name:
            agent = await am_service.get_agent_by_name(session, agent_name)
            if agent and agent.is_active:
                return agent
        # Legacy fallback: map the mode to a seeded Agent name.
        seeded_name = "drive_thru" if mode == "drive_thru" else "receptionist"
        agent = await am_service.get_agent_by_name(session, seeded_name)
        if agent and agent.is_active:
            return agent
    return None


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


async def _pump_deepgram_to_browser(deepgram_ws, client_ws: WebSocket, agent: Agent | None):
    """Deepgram -> Browser. Forward JSON events as text, binary audio as bytes.

    End-call triggers (any one of these fires once, then the pump drains):
      1. FunctionCallRequest for the registered end-call tool (primary — LLM tool calling).
      2. Assistant ConversationText ending in a farewell phrase (fallback).
      3. Dead air: AgentAudioDone followed by >DEAD_AIR_TIMEOUT s of silence.

    `agent` carries the tools used by `_handle_function_call` to resolve the
    handler_key per function name. None when running on the legacy fallback.
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
                await _handle_function_call(deepgram_ws, client_ws, msg, ended, agent)
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


async def _send_function_response(
    deepgram_ws, func_id: str, func_name: str, result: dict
) -> None:
    """Send a FunctionCallResponse envelope back to Deepgram.

    `result` is a dict; it is JSON-encoded twice (once to make the `content`
    string, once more for the envelope), matching Deepgram's wire format.
    """
    await deepgram_ws.send(
        json.dumps(
            {
                "type": "FunctionCallResponse",
                "id": func_id,
                "name": func_name,
                "content": json.dumps(result),
            }
        )
    )


async def _handle_function_call(
    deepgram_ws,
    client_ws: WebSocket,
    msg: dict,
    ended: asyncio.Event,
    agent: Agent | None,
) -> None:
    """Dispatch a FunctionCallRequest to the registered handler and reply.

    Looks up each requested tool by name on the active `Agent`, resolves its
    `handler_key` to a registered async callable, and runs it with a
    `ToolCallContext` that carries an `on_terminate` closure attached to this
    relay's `ended` event — so e.g. `system.end_call` ends the call without the
    relay needing to hardcode `gja_end_call`.

    Deepgram sends `functions: [...]` (an array); we iterate every entry and
    send one FunctionCallResponse per call.
    """
    # Build a name -> handler_key map for this agent once per request.
    tool_map: dict[str, str] = {}
    if agent is not None:
        for t in agent.tools:
            if t.is_active:
                tool_map[t.name] = t.handler_key

    async def _on_terminate(reason: str = "goodbye") -> None:
        """Closure the end-call handler calls to actually tear down the call."""
        if not ended.is_set():
            ended.set()
            asyncio.create_task(_send_end_call(client_ws, reason))

    functions = msg.get("functions", [])
    for func in functions:
        func_id = func.get("id", "")
        func_name = func.get("name", "")

        try:
            arguments = json.loads(func.get("arguments", "{}"))
        except (TypeError, ValueError):
            arguments = {}

        handler_key = tool_map.get(func_name)
        handler = get_handler(handler_key) if handler_key else None
        if handler is None:
            print(f"Unknown function call (no handler for {func_name!r})")
            await _send_function_response(
                deepgram_ws,
                func_id,
                func_name,
                {"error": f"No handler registered for tool {func_name!r}"},
            )
            continue

        ctx = ToolCallContext(tool_name=func_name, on_terminate=_on_terminate)
        print(f"{func_name} invoked (handler={handler_key}) with {arguments}")
        try:
            result = await handler(ctx, arguments)
        except (ValueError, TypeError) as e:
            result = {"error": str(e)}
        except Exception as e:
            print(f"Handler {handler_key} for {func_name} failed: {e}")
            result = {"error": f"Internal error in {func_name}"}

        await _send_function_response(deepgram_ws, func_id, func_name, result)
        if isinstance(result, dict) and "error" in result:
            print(f"  {func_name} → error: {result['error']}")
        elif isinstance(result, dict) and "order_id" in result:
            print(
                f"  {func_name} → order#{result.get('order_id')} "
                f"status={result.get('status')} "
                f"total={result.get('total_cents')}c "
                f"lines={len(result.get('items', []))}"
            )


async def relay(client_ws: WebSocket) -> None:
    """Run the full Deepgram Voice Agent session for one connected browser."""
    # Persona/mode (legacy) or agent_id/agent_name (new) arrive as the first
    # client message — too large for the URL.
    persona, mode, agent_id, agent_name = await _read_init_from_client(client_ws)

    agent = await _resolve_agent(persona, mode, agent_id, agent_name)
    if agent is not None:
        # Eager-load the agent's tools so the relay dispatcher can read them
        # without an extra round-trip per FunctionCallRequest.
        async with AsyncSessionLocal() as session:
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            stmt = (
                select(Agent).options(selectinload(Agent.tools)).where(Agent.id == agent.id)
            )
            res = await session.execute(stmt)
            fresh = res.scalar_one_or_none()
            if fresh is not None:
                agent = fresh
        settings_payload = am_service.assemble_settings(agent)
        # The browser resolves caller-context placeholders ({{name}}, {{email}},
        # {{phone}}) against the name/email/phone input fields and sends the
        # resolved persona in the Init frame. When present, it overrides the
        # raw DB template as the prompt — otherwise those substitutions (done
        # client-side) would be silently discarded on the DB-agent path. The
        # date tags are resolved server-side via render_persona regardless.
        if persona:
            from app.features.agent.render import render_persona
            settings_payload["agent"]["think"]["prompt"] = render_persona(persona)
        print(
            f"Relay using DB agent id={agent.id} name={agent.name!r} "
            f"tools={[t.name for t in agent.tools]}"
        )
    else:
        # Fall back to legacy constants if the dashboard hasn't seeded yet.
        drive_thru = mode == "drive_thru"
        settings_payload = legacy.build_settings(
            persona_or_drive_thru_fallback(persona, mode), drive_thru=drive_thru
        )
        print(
            f"Relay using LEGACY settings (no active agent for mode={mode!r})."
        )

    headers = {"Authorization": f"Token {Config.DEEPGRAM_API_KEY}"}

    try:
        async with websockets.connect(DEEPGRAM_AGENT_WS_URL, additional_headers=headers) as deepgram_ws:
            print(f"Connected to Deepgram Voice Agent API (mode={mode}).")

            # Handshake: Welcome -> Settings -> SettingsApplied
            await _wait_for_welcome(deepgram_ws)
            await _send_settings_and_wait(deepgram_ws, settings_payload)

            # Audio pumps run only after the handshake completes.
            task_client = asyncio.create_task(_pump_browser_to_deepgram(client_ws, deepgram_ws))
            task_deepgram = asyncio.create_task(
                _pump_deepgram_to_browser(deepgram_ws, client_ws, agent)
            )

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


def persona_or_drive_thru_fallback(persona: str, mode: str) -> str:
    """Pick the persona for the legacy fallback path."""
    if persona:
        return persona
    return legacy.DEFAULT_DRIVE_THRU_PERSONA if mode == "drive_thru" else legacy.DEFAULT_PERSONA
