"""Idempotent seeder for the canonical Agent + Tool rows.

Reproduces today's hardcoded behavior byte-for-byte by reading the
`GJA_*_TOOL` constants from `features/agent/settings.py` and the
`DEFAULT_*_PERSONA`/`GREETING` constants, so the seeded `receptionist` and
`drive_thru` agents behave identically to the legacy constants-based path.

This runs at startup AFTER the RBAC + agent_management migrations, and after
`seed_if_empty` for the menu (the menu tools need menu data).

Skip-on-existing by name; running twice is safe.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.agent import settings as legacy
from app.features.agent_management.models import Agent, Tool
from app.features.agent_management.service import (
    assign_tools,
    get_agent_by_name,
    get_tool_by_name,
)


async def _ensure_tool(session: AsyncSession, tool_dict: dict, handler_key: str) -> Tool:
    name = tool_dict["name"]
    tool = await get_tool_by_name(session, name)
    if tool is None:
        tool = Tool(
            name=name,
            description=tool_dict["description"],
            parameters=tool_dict["parameters"],
            handler_key=handler_key,
            is_active=True,
        )
        session.add(tool)
        await session.flush()
    return tool


async def seed_if_empty(session: AsyncSession) -> None:
    """Create the canonical Tools + Agents if missing. Idempotent by name."""
    # ── System ──────────────────────────────────────────────────────────
    end_call = await _ensure_tool(session, legacy.GJA_END_CALL_TOOL, "system.end_call")

    # ── Menu / Drive-thru ───────────────────────────────────────────────
    get_menu = await _ensure_tool(session, legacy.GJA_GET_MENU_TOOL, "menu.list")
    create_order = await _ensure_tool(session, legacy.GJA_CREATE_ORDER_TOOL, "menu.create_order")
    add_item = await _ensure_tool(session, legacy.GJA_ADD_ITEM_TOOL, "menu.add_item")
    update_item = await _ensure_tool(session, legacy.GJA_UPDATE_ITEM_TOOL, "menu.update_item")
    finalize_order = await _ensure_tool(
        session, legacy.GJA_FINALIZE_ORDER_TOOL, "menu.finalize_order"
    )

    # ── Booking / Receptionist ──────────────────────────────────────────
    contact_get = await _ensure_tool(session, legacy.GJA_CONTACT_GET_TOOL, "booking.contact_get")
    contact_create = await _ensure_tool(
        session, legacy.GJA_CONTACT_CREATE_TOOL, "booking.contact_create"
    )
    check_availability = await _ensure_tool(
        session, legacy.GJA_CHECK_AVAILABILITY_TOOL, "booking.check_availability"
    )
    create_event = await _ensure_tool(
        session, legacy.GJA_CREATE_EVENT_TOOL, "booking.create_event"
    )

    # ── receptionist (with booking tools) ───────────────────────────────
    rex = await get_agent_by_name(session, "receptionist")
    if rex is None:
        rex = Agent(
            name="receptionist",
            description="Default AI receptionist (Kinetic Innovative Staffing).",
            persona=legacy.DEFAULT_PERSONA,
            greeting=legacy.DEFAULT_GREETING,
        )
        session.add(rex)
        await session.flush()
        await assign_tools(
            session,
            rex,
            [
                contact_get.id,
                contact_create.id,
                check_availability.id,
                create_event.id,
                end_call.id,
            ],
        )
    else:
        # Existing receptionist — ensure all booking tools are assigned
        # (idempotent: assign_tools sets membership, doesn't duplicate).
        await assign_tools(
            session,
            rex,
            [
                contact_get.id,
                contact_create.id,
                check_availability.id,
                create_event.id,
                end_call.id,
            ],
        )

    # ── drive_thru (Burger Barn) ────────────────────────────────────────
    drive = await get_agent_by_name(session, "drive_thru")
    if drive is None:
        drive = Agent(
            name="drive_thru",
            description="Burger Barn drive-thru cashier persona.",
            persona=legacy.DEFAULT_DRIVE_THRU_PERSONA,
            greeting=legacy.DEFAULT_DRIVE_THRU_GREETING,
        )
        session.add(drive)
        await session.flush()
        await assign_tools(
            session,
            drive,
            [get_menu.id, create_order.id, add_item.id, update_item.id, finalize_order.id, end_call.id],
        )

    await session.commit()
