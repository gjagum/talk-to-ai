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
from app.features.booking import service as booking_service
from app.features.booking.schemas import (
    AvailabilityRequest,
    BookingCreate,
    ContactCreate,
)
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


# ── Booking / Receptionist ─────────────────────────────────────────────────


def _serialize_contact(contact) -> dict:
    """Serialize a Contact ORM row into the dict returned to the LLM."""
    return {
        "id": contact.id,
        "full_name": contact.full_name,
        "email": contact.email,
        "phone": contact.phone,
        "timezone": contact.timezone,
        "city": contact.city,
    }


def _serialize_booking(booking) -> dict:
    """Serialize a Booking ORM row into the dict returned to the LLM."""
    return {
        "id": booking.id,
        "contact_id": booking.contact_id,
        "title": booking.title,
        "requested_at": booking.requested_at.isoformat() if booking.requested_at else None,
        "duration_minutes": booking.duration_minutes,
        "status": booking.status,
        "notes": booking.notes,
        "contact": {
            "full_name": booking.contact.full_name if booking.contact else None,
            "email": booking.contact.email if booking.contact else None,
            "timezone": booking.contact.timezone if booking.contact else None,
        },
    }


@register("booking.contact_get", "Find a contact by email/phone")
async def _contact_get(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            contact = await booking_service.find_contact(
                session,
                email=arguments.get("email"),
                phone=arguments.get("phone"),
            )
            if contact is None:
                return {"found": False, "contact": None}
            return {"found": True, "contact": _serialize_contact(contact)}
        except Exception as e:
            await session.rollback()
            print(f"booking.contact_get failed: {e}")
            return {"error": f"Internal error: {e}"}


@register("booking.contact_create", "Create or update a contact (upsert by email)")
async def _contact_create(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            contact = await booking_service.get_or_create_contact(
                session,
                email=arguments["email"],
                full_name=arguments.get("full_name"),
                phone=arguments.get("phone"),
                timezone_name=arguments.get("timezone"),
                city=arguments.get("city"),
            )
            await session.commit()
            return _serialize_contact(contact)
        except (ValueError, TypeError, KeyError) as e:
            await session.rollback()
            return {"error": str(e)}
        except Exception as e:
            await session.rollback()
            print(f"booking.contact_create failed: {e}")
            return {"error": f"Internal error: {e}"}


@register("booking.check_availability", "Check available slots for a date")
async def _check_availability(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            request = AvailabilityRequest(
                date=arguments["date"],
                timezone=arguments.get("timezone", "UTC"),
            )
            slots = await booking_service.check_availability(session, request)
            return {
                "date": arguments["date"],
                "timezone": arguments.get("timezone", "UTC"),
                "consultant_timezone": booking_service.CONSULTANT_TIMEZONE,
                "slots": [
                    {
                        "start": slot.start.isoformat(),
                        "end": slot.end.isoformat(),
                    }
                    for slot in slots
                ],
            }
        except (ValueError, TypeError, KeyError) as e:
            await session.rollback()
            return {"error": str(e)}
        except Exception as e:
            await session.rollback()
            print(f"booking.check_availability failed: {e}")
            return {"error": f"Internal error: {e}"}


@register("booking.create_event", "Book an appointment (discovery/preso call)")
async def _create_event(ctx: ToolCallContext, arguments: dict) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            payload = BookingCreate(
                contact_id=int(arguments["contact_id"]),
                requested_at=arguments["requested_at"],
                duration_minutes=int(arguments.get("duration_minutes", 30)),
                title=arguments.get("title"),
                notes=arguments.get("notes"),
            )
            booking = await booking_service.create_booking(session, payload)
            await session.commit()
            # Refresh to populate the contact relationship for serialization.
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            from app.features.booking.models import Booking
            stmt = select(Booking).where(Booking.id == booking.id).options(selectinload(Booking.contact))
            result = await session.execute(stmt)
            booking = result.scalar_one()
            return {"success": True, "booking": _serialize_booking(booking)}
        except (ValueError, TypeError, KeyError) as e:
            await session.rollback()
            return {"error": str(e)}
        except Exception as e:
            await session.rollback()
            print(f"booking.create_event failed: {e}")
            return {"error": f"Internal error: {e}"}
