"""Pydantic v2 request/response schemas for the menu-ordering domain.

Layered: `_Create`/`_Add` (input) → DB model → `_Read` (output). Money is
`*_cents: int` everywhere (UI divides by 100). Status is a closed enum of six
literals matching models.OrderStatus.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OrderStatusLiteral = Literal[
    "draft", "received", "in_progress", "ready", "completed", "cancelled"
]
OrderTypeLiteral = Literal["drive_thru", "takeout", "dine_in"]


# ---------------------------------------------------------------------------
# Menu items
# ---------------------------------------------------------------------------
class MenuItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    price_cents: int
    category: str | None = None
    is_available: bool


# ---------------------------------------------------------------------------
# Order items
# ---------------------------------------------------------------------------
class OrderItemAdd(BaseModel):
    """Add a line to an order. Shared by the HTTP endpoint and the
    `gja_add_item` Deepgram tool."""

    menu_item_id: int = Field(..., description="ID of the MenuItem to add")
    quantity: int = Field(default=1, ge=1)
    notes: str | None = Field(default=None, description="Free-text modifiers, e.g. 'no pickles'")


class OrderItemUpdate(BaseModel):
    """Update (or remove) a line. quantity=0 removes the line."""

    quantity: int | None = Field(default=None, ge=0)
    notes: str | None = None


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int | None = None
    name_snapshot: str
    unit_price_cents: int
    quantity: int
    notes: str | None = None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class OrderCreate(BaseModel):
    """Optional fields when creating an empty draft order."""

    customer_name: str | None = None
    customer_phone: str | None = None
    order_type: OrderTypeLiteral = "drive_thru"
    notes: str | None = None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatusLiteral
    customer_name: str | None = None
    customer_phone: str | None = None
    order_type: OrderTypeLiteral
    notes: str | None = None
    total_cents: int
    items: list[OrderItemRead] = []
    created_at: datetime
    updated_at: datetime


class OrderStatusUpdate(BaseModel):
    status: OrderStatusLiteral


class OrderFinalize(BaseModel):
    """Finalize a draft order (sets status=received) and capture customer info."""

    customer_name: str | None = None
    customer_phone: str | None = None
    order_type: OrderTypeLiteral | None = None
    notes: str | None = None
