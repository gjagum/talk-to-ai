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
from app.features.agent.settings import (
    DEFAULT_DRIVE_THRU_PERSONA,
    DEFAULT_PERSONA,
    build_settings,
)
from app.features.menu import service as menu_service
from app.features.menu.schemas import (
    OrderCreate,
    OrderItemAdd,
    OrderItemUpdate,
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


async def _read_init_from_client(client_ws: WebSocket) -> tuple[str, str]:
    """Wait for the browser's first text message containing the persona + mode.

    The persona (system prompt) is too large to send via URL query string —
    it can easily exceed the WebSocket handshake's request-line size limit. So
    the browser sends it as the first JSON text frame after the socket opens.
    Expected message:
      {"type": "Init", "persona": "<system prompt>", "mode": "receptionist"}
    `mode` selects the persona default / tool set; currently supports
    `receptionist` (default) and `drive_thru`.
    Returns (persona, mode).
    """
    mode = "receptionist"
    try:
        while True:
            msg = await client_ws.receive()
            if "text" in msg and msg["text"] is not None:
                payload = json.loads(msg["text"])
                if payload.get("type") == "Init":
                    persona = payload.get("persona") or ""
                    mode = (payload.get("mode") or "receptionist").strip()
                    if persona:
                        return persona, mode
                    break  # empty persona → fall through to default
    except WebSocketDisconnect:
        raise
    except Exception as e:
        print(f"Error reading Init/persona from client: {e}")

    # Empty persona → use the default for the selected mode.
    default_persona = (
        DEFAULT_DRIVE_THRU_PERSONA if mode == "drive_thru" else DEFAULT_PERSONA
    )
    return default_persona, mode


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


async def _run_menu_tool(func_name: str, arguments: dict) -> dict:
    """Execute one menu tool inside its own session and commit.

    The WebSocket relay is not inside FastAPI's request scope, so it does not
    use `get_db`. Each tool call opens a fresh `AsyncSessionLocal` session,
    runs the corresponding `menu.service` function, commits, and returns a
    small dict that becomes the FunctionCallResponse content. On ValidationError
    / ValueError the returned dict carries an `error` key (no exception escapes
    the WebSocket loop); the LLM reads the error and adapts its next turn.
    """
    async with AsyncSessionLocal() as session:
        try:
            if func_name == "gja_get_menu":
                category = arguments.get("category")
                items = await menu_service.list_menu(
                    session, category=category, available_only=True
                )
                return {
                    "items": [
                        {
                            "id": it.id,
                            "name": it.name,
                            "description": it.description,
                            "price_cents": it.price_cents,
                            "category": it.category,
                            "is_available": it.is_available,
                        }
                        for it in items
                    ]
                }

            if func_name == "gja_create_order":
                order_type = arguments.get("order_type", "drive_thru")
                payload = OrderCreate(order_type=order_type)
                order = await menu_service.create_order(session, payload)
                await session.commit()
                return {"order_id": order.id, "status": order.status, "items": [], "total_cents": 0}

            if func_name == "gja_add_item":
                order_id = int(arguments.get("order_id", 0))
                menu_item_id = int(arguments.get("menu_item_id", 0))
                quantity = int(arguments.get("quantity", 1) or 1)
                notes = arguments.get("notes")
                payload = OrderItemAdd(
                    menu_item_id=menu_item_id, quantity=quantity, notes=notes
                )
                order = await menu_service.add_item_to_order(session, order_id, payload)
                await session.commit()
                return _serialize_order(order)

            if func_name == "gja_update_item":
                order_id = int(arguments.get("order_id", 0))
                item_id = int(arguments.get("item_id", 0))
                quantity = arguments.get("quantity")
                notes = arguments.get("notes")
                payload = OrderItemUpdate(
                    quantity=int(quantity) if quantity is not None else None,
                    notes=notes,
                )
                order = await menu_service.update_order_item(
                    session, order_id, item_id, payload
                )
                await session.commit()
                return _serialize_order(order)

            if func_name == "gja_finalize_order":
                order_id = int(arguments.get("order_id", 0))
                order = await menu_service.finalize_order(
                    session,
                    order_id,
                    customer_name=arguments.get("customer_name"),
                    customer_phone=arguments.get("customer_phone"),
                    order_type=arguments.get("order_type"),
                    notes=arguments.get("notes"),
                )
                await session.commit()
                return _serialize_order(order)

            return {"error": f"Unknown menu tool: {func_name}"}
        except (ValueError, TypeError) as e:
            # Bad arguments: missing item, wrong status, empty finalize, etc.
            # Rollback and surface as an error result — the LLM will adapt.
            await session.rollback()
            return {"error": str(e)}
        except Exception as e:
            await session.rollback()
            print(f"Menu tool {func_name} failed: {e}")
            return {"error": f"Internal error in {func_name}"}


def _serialize_order(order) -> dict:
    """Flatten an Order ORM object to a dict for FunctionCallResponse.

    Kept inline (next to the relay) rather than in schemas because the WebSocket
    path can't reuse the Pydantic response_model serialization — we want a
    plain dict here. `order.items` must be eager-loaded (service does this).
    """
    return {
        "order_id": order.id,
        "status": order.status,
        "customer_name": order.customer_name,
        "order_type": order.order_type,
        "total_cents": order.total_cents,
        "items": [
            {
                "item_id": it.id,
                "menu_item_id": it.menu_item_id,
                "name": it.name_snapshot,
                "unit_price_cents": it.unit_price_cents,
                "quantity": it.quantity,
                "notes": it.notes,
            }
            for it in order.items
        ],
    }


_MENU_TOOLS = (
    "gja_get_menu",
    "gja_create_order",
    "gja_add_item",
    "gja_update_item",
    "gja_finalize_order",
)


async def _handle_function_call(deepgram_ws, client_ws: WebSocket, msg: dict, ended: asyncio.Event) -> None:
    """Dispatch a FunctionCallRequest to the correct tool and reply.

    Deepgram sends `functions: [...]` (an array); we iterate every entry and
    send one FunctionCallResponse per call. `gja_end_call` is the only tool
    that also tears down the call — every other tool just executes and replies.
    """
    functions = msg.get("functions", [])
    for func in functions:
        func_id = func.get("id", "")
        func_name = func.get("name", "")

        try:
            arguments = json.loads(func.get("arguments", "{}"))
        except (TypeError, ValueError):
            arguments = {}

        # ── terminal tool: end the call ──
        if func_name == "gja_end_call":
            reason = arguments.get("reason", "goodbye")
            print(f"gja_end_call invoked (reason={reason})")

            await _send_function_response(
                deepgram_ws, func_id, func_name, {"status": "ok", "reason": reason}
            )

            ended.set()
            asyncio.create_task(_send_end_call(client_ws, reason))
            continue

        # ── drive-thru ordering tools ──
        if func_name in _MENU_TOOLS:
            print(f"{func_name} invoked with {arguments}")
            result = await _run_menu_tool(func_name, arguments)
            await _send_function_response(deepgram_ws, func_id, func_name, result)
            if "error" in result:
                print(f"  {func_name} → error: {result['error']}")
            else:
                # Brief success log — whatever the LLM most needs to confirm.
                if "order_id" in result:
                    print(
                        f"  {func_name} → order#{result.get('order_id')} "
                        f"status={result.get('status')} "
                        f"total={result.get('total_cents')}c "
                        f"lines={len(result.get('items', []))}"
                    )
            continue

        print(f"Unknown function call: {func_name}")


async def relay(client_ws: WebSocket) -> None:
    """Run the full Deepgram Voice Agent session for one connected browser."""
    # Persona + mode arrive as the first client message (too large for the URL).
    persona, mode = await _read_init_from_client(client_ws)
    drive_thru = mode == "drive_thru"

    headers = {"Authorization": f"Token {Config.DEEPGRAM_API_KEY}"}

    try:
        async with websockets.connect(DEEPGRAM_AGENT_WS_URL, additional_headers=headers) as deepgram_ws:
            print(f"Connected to Deepgram Voice Agent API (mode={mode}).")

            # Handshake: Welcome -> Settings -> SettingsApplied
            await _wait_for_welcome(deepgram_ws)
            await _send_settings_and_wait(
                deepgram_ws, build_settings(persona, drive_thru=drive_thru)
            )

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
