"""Pydantic v2 request/response schemas for the booking domain.

Layered: `_Create` (input) → DB model → `_Read` (output, touched up to DB rows).

Time fields use ISO-8601 strings. `requested_at` is timezone-aware UTC on the
wire; `timezone` on Contact/AvailabilityRequest is an IANA tz name (e.g.
"America/New_York", "Australia/Sydney", "Asia/Manila").
"""
from datetime import datetime
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
class ContactCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    timezone: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=120)


class ContactRead(BaseModel):
    """Read shape for a Contact.

    `email` is validated on write (ContactCreate uses EmailStr), but legacy or
    agent-written rows can hold malformed values (e.g. an unrendered `{{email}}`
    placeholder). A single bad row would otherwise 500 the whole bookings list,
    so on read we coerce invalid emails to a placeholder rather than raising.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: str | None = None
    timezone: str | None = None
    city: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("email", mode="before")
    @classmethod
    def _coerce_invalid_email(cls, v):
        if v is None:
            return "(invalid)"
        try:
            validate_email(v, check_deliverability=False)
        except EmailNotValidError:
            return "(invalid)"
        return str(v)


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
class BookingCreate(BaseModel):
    """Create a booking. Either contact_id (existing contact) OR contact fields
    (full_name + email) must be supplied; if contact fields are given, the
    contact is created-or-fetched by email first.

    `requested_at` is timezone-aware UTC ISO-8601 (e.g.
    "2026-06-26T03:00:00+00:00"). Requester-local time is conveyed via
    `requester_timezone` so the agent/UI can render in local time.
    """

    contact_id: int | None = None
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    timezone: str | None = None
    city: str | None = None
    requested_at: datetime
    duration_minutes: int = Field(default=30, ge=5, le=480)
    title: str | None = None
    notes: str | None = None


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_id: int
    title: str | None = None
    requested_at: datetime
    duration_minutes: int
    status: Literal["pending", "confirmed", "cancelled", "completed"]
    notes: str | None = None
    created_at: datetime
    contact: ContactRead


class BookingStatusUpdate(BaseModel):
    status: Literal["pending", "confirmed", "cancelled", "completed"]


# ---------------------------------------------------------------------------
# Availability (AI-caller tool: gja_check_availability)
# ---------------------------------------------------------------------------
class AvailabilityRequest(BaseModel):
    """GET /availability?date=YYYY-MM-DD&timezone=America/New_York — compute
    consultant working-hour slots for that date, converted to the requester's
    timezone, excluding slots already held by pending/confirmed bookings."""

    date: str = Field(..., description="ISO date YYYY-MM-DD in requester's local tz")
    timezone: str = Field(default="UTC", description="IANA tz of the requester")


class TimeSlot(BaseModel):
    """An available 30-min slot, returned in the *requester's* timezone."""

    start: datetime
    end: datetime


class AvailabilityResponse(BaseModel):
    date: str
    timezone: str
    consultant_timezone: str
    slots: list[TimeSlot]
