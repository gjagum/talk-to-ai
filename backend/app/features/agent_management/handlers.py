"""Tool handler registry — maps a Tool's `handler_key` string to the Python
function that actually executes it.

Why this pattern
----------------
In the old relay (`features/agent/relay.py`), tool dispatch was a giant
`if func_name == "gja_..."` chain. That doesn't scale: every new tool needed a
code change in the relay, and the relay had to know every tool's name.

Here, the ADMIN owns the *LLM-facing* description/schema (editable per agent in
the dashboard), but the CODE owns the *implementation* (a registered async
callable). The two are linked only by the `handler_key` string the admin
chooses from a dropdown. The relay looks up `tool.handler_key` → calls
`HANDLERS[handler_key]`. No relay edits needed for new tools that reuse an
existing handler.

`system.end_call` is special: it's the one tool whose execution has a
side-effect outside the DB (terminates the relay). It's exposed here as a
normal handler keyed by `"system.end_call"`, but the relay recognises the key
and also signals pump shutdown via the `on_terminate` callback passed in the
ToolCallContext.

Open its own AsyncSession per call (mirrors the legacy `_run_menu_tool`)
because the relay is not inside FastAPI's request scope.
"""
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.core.database import AsyncSessionLocal
from app.features.menu import service as menu_service
from app.features.menu.schemas import (
    OrderCreate,
    OrderItemAdd,
    OrderItemUpdate,
)

# ── Context passed to every handler ────────────────────────────────────────


@dataclass
class ToolCallContext:
    """Runtime context handed to each handler.

    - `tool_name`: the Deepgram-facing function name (e.g. "gja_get_menu").
      Multiple tools can share one handler_key, so the handler may need to
      know which name the LLM used.
    - `on_terminate`: callable the handler can invoke to tear down the relay
      (only `system.end_call` uses this in practice).
    """

    tool_name: str
    on_terminate: Callable[[str], Awaitable[None]] | None = None


# Handler signature: (context, arguments) -> result dict that becomes the
# FunctionCallResponse content.
ToolHandler = Callable[[ToolCallContext, dict], Awaitable[dict[str, Any]]]

_HANDLERS: dict[str, ToolHandler] = {}
_HANDLER_LABELS: dict[str, str] = {}


def register(key: str, label: str) -> Callable[[ToolHandler], ToolHandler]:
    """Decorator to register a handler under `key` with a UI label."""

    def _wrap(fn: ToolHandler) -> ToolHandler:
        _HANDLERS[key] = fn
        _HANDLER_LABELS[key] = label
        return fn

    return _wrap


def get_handler(handler_key: str) -> ToolHandler | None:
    return _HANDLERS.get(handler_key)


def list_handler_keys() -> list[tuple[str, str]]:
    """Return (key, label) pairs for the Tools form dropdown."""
    return sorted(_HANDLER_LABELS.items(), key=lambda kv: kv[0])


# ── Helpers ────────────────────────────────────────────────────────────────


def _serialize_order(order) -> dict:
    """Mirror of relay._serialize_order for FunctionCallResponse bodies."""
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


# ── System ─────────────────────────────────────────────────────────────────


@register("system.end_call", "End the call (terminal)")
async def _end_call(ctx: ToolCallContext, arguments: dict) -> dict:
    reason = arguments.get("reason", "goodbye")
    if ctx.on_terminate is not None:
        await ctx.on_terminate(reason)
    return {"status": "ok", "reason": reason}


# ── Menu ───────────────────────────────────────────────────────────────────


@register("menu.list", "List the menu (optionally by category)")
async def _menu_list(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            category = arguments.get("category")
            items = await menu_service.list_menu(session, category=category, available_only=True)
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
        except Exception as e:
            await session.rollback()
            print(f"menu.list failed: {e}")
            return {"error": f"Internal error: {e}"}


@register("menu.create_order", "Create a new (empty) order")
async def _menu_create_order(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            order_type = arguments.get("order_type", "drive_thru")
            order = await menu_service.create_order(session, OrderCreate(order_type=order_type))
            await session.commit()
            return {"order_id": order.id, "status": order.status, "items": [], "total_cents": 0}
        except (ValueError, TypeError) as e:
            await session.rollback()
            return {"error": str(e)}


@register("menu.add_item", "Add a line item to an order")
async def _menu_add_item(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            payload = OrderItemAdd(
                menu_item_id=int(arguments.get("menu_item_id", 0)),
                quantity=int(arguments.get("quantity", 1) or 1),
                notes=arguments.get("notes"),
            )
            order = await menu_service.add_item_to_order(
                session, int(arguments.get("order_id", 0)), payload
            )
            await session.commit()
            return _serialize_order(order)
        except (ValueError, TypeError) as e:
            await session.rollback()
            return {"error": str(e)}


@register("menu.update_item", "Update or remove a line item")
async def _menu_update_item(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            qty = arguments.get("quantity")
            payload = OrderItemUpdate(
                quantity=int(qty) if qty is not None else None,
                notes=arguments.get("notes"),
            )
            order = await menu_service.update_order_item(
                session,
                int(arguments.get("order_id", 0)),
                int(arguments.get("item_id", 0)),
                payload,
            )
            await session.commit()
            return _serialize_order(order)
        except (ValueError, TypeError) as e:
            await session.rollback()
            return {"error": str(e)}


@register("menu.finalize_order", "Lock in a draft order (status -> received)")
async def _menu_finalize_order(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            order = await menu_service.finalize_order(
                session,
                int(arguments.get("order_id", 0)),
                customer_name=arguments.get("customer_name"),
                customer_phone=arguments.get("customer_phone"),
                order_type=arguments.get("order_type"),
                notes=arguments.get("notes"),
            )
            await session.commit()
            return _serialize_order(order)
        except (ValueError, TypeError) as e:
            await session.rollback()
            return {"error": str(e)}
