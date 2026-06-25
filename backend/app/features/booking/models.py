"""SQLAlchemy ORM models for the booking domain.

Two related entities:
  - Contact : a prospect (name, email unique, phone, timezone, city).
  - Booking : a scheduled call FK'd to a contact (requested_at UTC-aware,
              duration, status, notes, timestamps).

Timestamps use timezone-aware UTC. Contact.email is unique so AI-caller tool
`gja_contact_get` can look up an existing prospect by email/phone.

These models import Base (app.core.database) and are registered on
Base.metadata at import time; app.main imports this module before running
create_all.
"""
from datetime import datetime, timezone

from sqlalchemy import (
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


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Always store as timezone-aware UTC; convert at the API boundary.
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    # pending | confirmed | cancelled | completed
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="bookings")


# Convenience constants — mirrored by the schema enum/default.
BookingStatus = ("pending", "confirmed", "cancelled", "completed")
