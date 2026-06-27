"""SQLAlchemy ORM models for the menu-ordering (drive-thru) domain.

Three related entities:
  - MenuItem : a sellable item on the menu (name, price in integer cents,
               category, availability flag).
  - Order    : a single customer order. Starts as a `draft` while the voice
               agent builds it up, transitions through
               received -> in_progress -> ready -> completed (or cancelled).
               `total_cents` is recomputed from line items on every mutation.
  - OrderItem: a line item within an order. Snapshots `name_snapshot` and
               `unit_price_cents` from the MenuItem at add-time so historical
               orders stay readable if the menu changes later.

Money is stored as integer cents to avoid float rounding drift. Timestamps are
timezone-aware UTC. These models register on Base.metadata at import time;
app.main imports this module before create_all runs.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    """Timezone-aware UTC 'now' for column defaults."""
    return datetime.now(timezone.utc)


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Money stored as integer cents (DB & API contract); UI divides by 100.
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # draft -> received -> in_progress -> ready -> completed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # drive_thru | takeout | dine_in
    order_type: Mapped[str] = mapped_column(String(20), default="drive_thru", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Recomputed from line items on every add/update/remove mutation.
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable so Deleting a MenuItem doesn't lose historical line items in
    # future versions; v1 never deletes menu items though.
    menu_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Snapshot of the MenuItem at add-time so historical orders stay readable.
    name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")
    menu_item: Mapped["MenuItem | None"] = relationship()


# Convenience constants — mirrored by the schema enums/defaults.
OrderStatus = (
    "draft",        # agent is still adding items
    "received",     # finalized by the caller/agent
    "in_progress",  # kitchen is preparing
    "ready",        # ready for pickup
    "completed",    # handed off
    "cancelled",
)
