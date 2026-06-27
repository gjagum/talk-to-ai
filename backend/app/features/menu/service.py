"""Async business logic for the menu-ordering domain.

Mirrors the `booking/service.py` pattern: pure async functions, each taking an
`AsyncSession` plus typed args and returning ORM objects. The router (HTTP)
and the WebSocket relay (Deepgram tool dispatch) each commit/refresh after
calling; *this* layer only flushes so it can populate auto-generated ids.

Total price (`Order.total_cents`) is recomputed from line items on every
add/update/remove. Optional row-level pessimistic locking (`for_update=True`)
serializes concurrent mutations from multiple tool calls within one draft.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.menu.models import MenuItem, Order, OrderItem
from app.features.menu.schemas import (
    OrderCreate,
    OrderItemAdd,
    OrderItemUpdate,
)


# ---------------------------------------------------------------------------
# Menu items
# ---------------------------------------------------------------------------
async def list_menu(
    session: AsyncSession,
    *,
    category: str | None = None,
    available_only: bool = True,
) -> list[MenuItem]:
    """List menu items, optionally filtered by category and/or availability."""
    stmt = select(MenuItem).order_by(MenuItem.category, MenuItem.name)
    if category:
        stmt = stmt.where(MenuItem.category == category)
    if available_only:
        stmt = stmt.where(MenuItem.is_available.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_menu_item(session: AsyncSession, item_id: int) -> MenuItem | None:
    return (
        await session.execute(select(MenuItem).where(MenuItem.id == item_id))
    ).scalar_one_or_none()


async def find_menu_item_by_name(session: AsyncSession, name: str) -> MenuItem | None:
    """Case-insensitive name lookup. Backs tool/HTTP paths where the agent
    references an item by display name instead of id. Returns the first hit."""
    stmt = select(MenuItem).where(func.lower(MenuItem.name) == name.strip().lower())
    return (await session.execute(stmt)).scalars().first()


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
async def create_order(
    session: AsyncSession, payload: OrderCreate | None = None
) -> Order:
    """Insert an empty draft order. Flushes so order.id is populated."""
    payload = payload or OrderCreate()
    order = Order(
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        order_type=payload.order_type,
        notes=payload.notes,
        status="draft",
        total_cents=0,
    )
    session.add(order)
    await session.flush()
    return order


async def get_order(
    session: AsyncSession, order_id: int, *, for_update: bool = False
) -> Order | None:
    """Fetch one order with line items eager-loaded. `for_update` wraps the
    select in a row lock (`SELECT ... FOR UPDATE`) to serialize concurrent
    mutations during a drive-thru call."""
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_orders(
    session: AsyncSession, *, status_filter: str | None = None
) -> list[Order]:
    """List orders, optionally filtered by status, newest first."""
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Line-item mutations
# ---------------------------------------------------------------------------
def _recompute_total(order: Order) -> None:
    """Recompute order.total_cents from its in-memory items collection.
    OrderItem set in a relationship must be loaded already (we always use
    selectinload)."""
    order.total_cents = sum(
        item.unit_price_cents * item.quantity for item in order.items
    )


async def add_item_to_order(
    session: AsyncSession, order_id: int, payload: OrderItemAdd
) -> Order:
    """Add a line item to a draft order.

    - Resolves the MenuItem by id; raises ValueError if missing/unavailable.
    - Merges quantity into an existing line with the same menu_item_id + notes
      (so 'add a burger' twice doesn't create two rows).
    - Recomputes the order total.

    Uses row-level locking (`for_update=True`) to make concurrent tool calls
    within the same draft safe.
    """
    order = await get_order(session, order_id, for_update=True)
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order.status not in ("draft", "received"):
        raise ValueError(f"Cannot modify order {order_id} in status '{order.status}'")

    menu_item = await get_menu_item(session, payload.menu_item_id)
    if menu_item is None:
        raise ValueError(f"Menu item {payload.menu_item_id} not found")
    if not menu_item.is_available:
        raise ValueError(f"'{menu_item.name}' is currently unavailable")

    notes_normalized = (payload.notes or "").strip() or None
    # Merge into an existing identical line if present.
    for item in order.items:
        if item.menu_item_id == menu_item.id and (item.notes or "") == (
            notes_normalized or ""
        ):
            item.quantity += payload.quantity
            _recompute_total(order)
            await session.flush()
            return order

    order.items.append(
        OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            name_snapshot=menu_item.name,
            unit_price_cents=menu_item.price_cents,
            quantity=payload.quantity,
            notes=notes_normalized,
        )
    )
    _recompute_total(order)
    await session.flush()
    return order


async def update_order_item(
    session: AsyncSession, order_id: int, item_id: int, payload: OrderItemUpdate
) -> Order:
    """Update or remove an existing line. quantity=0 removes the line."""
    order = await get_order(session, order_id, for_update=True)
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order.status not in ("draft", "received"):
        raise ValueError(f"Cannot modify order {order_id} in status '{order.status}'")

    item = next((it for it in order.items if it.id == item_id), None)
    if item is None:
        raise ValueError(f"Line item {item_id} not found on order {order_id}")

    if payload.quantity is not None:
        if payload.quantity == 0:
            # Drop the line. Direct removal from the relationship triggers the
            # cascade; we also null out the FK which lets delete-orphan fire.
            order.items.remove(item)
            await session.delete(item)
        else:
            item.quantity = payload.quantity
    if payload.notes is not None:
        item.notes = payload.notes.strip() or None

    _recompute_total(order)
    await session.flush()
    return order


async def set_order_status(
    session: AsyncSession, order_id: int, new_status: str
) -> Order | None:
    """Advance/set an order's status (no extra validations for v1 — status
    transitions are free-form within the enum; the schema Literal enforces
    membership)."""
    order = await get_order(session, order_id)
    if order is None:
        return None
    order.status = new_status
    await session.flush()
    return order


async def finalize_order(
    session: AsyncSession,
    order_id: int,
    *,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    order_type: str | None = None,
    notes: str | None = None,
) -> Order:
    """Transition a draft to 'received' and capture optional customer info.

    Refuses to finalize empty orders (no items) or non-draft orders.
    """
    order = await get_order(session, order_id, for_update=True)
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order.status != "draft":
        raise ValueError(
            f"Order {order_id} is already '{order.status}' and cannot be finalized"
        )
    if not order.items:
        raise ValueError(f"Order {order_id} has no items — cannot finalize an empty order")

    order.status = "received"
    if customer_name:
        order.customer_name = customer_name
    if customer_phone:
        order.customer_phone = customer_phone
    if order_type:
        order.order_type = order_type
    if notes:
        order.notes = notes
    _recompute_total(order)
    await session.flush()
    return order
