"""REST endpoints for the menu-ordering domain.

Endpoints double as the AI-caller tool surface for drivers that go through
REST (the walk-in staff UI uses these; the voice agent goes through the
WebSocket relay which calls menu.service directly):

  GET    /menu                         list menu items (?category=&available=)
  GET    /menu/{item_id}               fetch one menu item
  GET    /orders                       list orders (?status=)
  POST   /orders                       create an empty draft order
  GET    /orders/{order_id}            fetch one order (+ line items)
  PATCH  /orders/{order_id}/status     update order status
  POST   /orders/{order_id}/items      add a line item
  PATCH  /orders/{order_id}/items/{id} update/remove a line item (quantity=0)
  POST   /orders/{order_id}/finalize   finalize draft -> received

All write endpoints commit their session. ValueError from the service layer
becomes HTTP 400 (logical failures like finalizing an empty order); missing
order/item becomes HTTP 404.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.menu import service
from app.features.menu.schemas import (
    MenuItemRead,
    OrderCreate,
    OrderFinalize,
    OrderItemAdd,
    OrderItemRead,
    OrderItemUpdate,
    OrderRead,
    OrderStatusUpdate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
@router.get("/menu", response_model=list[MenuItemRead])
async def list_menu(
    category: str | None = Query(default=None),
    available: bool | None = Query(default=True),
    session: AsyncSession = Depends(get_db),
):
    """List menu items, optionally filtered by category/availability."""
    return await service.list_menu(
        session, category=category, available_only=bool(available)
    )


@router.get("/menu/{item_id}", response_model=MenuItemRead)
async def get_menu_item(item_id: int, session: AsyncSession = Depends(get_db)):
    item = await service.get_menu_item(session, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    return item


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
@router.get("/orders", response_model=list[OrderRead])
async def list_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db),
):
    """List orders, optionally filtered by status, newest first."""
    return await service.list_orders(session, status_filter=status_filter)


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate | None = None, session: AsyncSession = Depends(get_db)
):
    """Create an empty draft order."""
    order = await service.create_order(session, payload)
    await session.commit()
    # Re-read with items populated (empty []) for the response.
    await session.refresh(order)
    return order


@router.get("/orders/{order_id}", response_model=OrderRead)
async def get_order(order_id: int, session: AsyncSession = Depends(get_db)):
    order = await service.get_order(session, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.patch("/orders/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update order status (draft|received|in_progress|ready|completed|cancelled)."""
    order = await service.set_order_status(session, order_id, payload.status)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    await session.commit()
    await session.refresh(order)
    return order


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------
@router.post("/orders/{order_id}/items", response_model=OrderRead)
async def add_order_item(
    order_id: int,
    payload: OrderItemAdd,
    session: AsyncSession = Depends(get_db),
):
    """Add a line item to a draft order."""
    try:
        order = await service.add_item_to_order(session, order_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await session.commit()
    await session.refresh(order)
    return order


@router.patch("/orders/{order_id}/items/{item_id}", response_model=OrderRead)
async def update_order_item(
    order_id: int,
    item_id: int,
    payload: OrderItemUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update a line item (quantity=0 removes it)."""
    try:
        order = await service.update_order_item(session, order_id, item_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await session.commit()
    await session.refresh(order)
    return order


@router.post("/orders/{order_id}/finalize", response_model=OrderRead)
async def finalize_order(
    order_id: int,
    payload: OrderFinalize | None = None,
    session: AsyncSession = Depends(get_db),
):
    """Finalize a draft order (status -> received)."""
    payload = payload or OrderFinalize()
    try:
        order = await service.finalize_order(
            session,
            order_id,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            order_type=payload.order_type,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await session.commit()
    await session.refresh(order)
    return order
