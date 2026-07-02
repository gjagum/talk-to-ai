"""Async business logic for the booking domain.

Mirrors the `voice/services/*` pattern: pure async functions imported by
router.py, each taking an `AsyncSession` plus typed args and returning ORM
objects. Endpoints commit; this layer does not.

Availability model:
  - Consultant working hours are defined in CONSULTANT_TIMEZONE (Asia/Manila,
    per the AI-caller persona).
  - For a requested date in the requester's timezone, we enumerate fixed
    working-hour slots in consultant-local time, drop any that overlap a
    confirmed booking, and convert each slot back to the requester's tz for
    display/return.

All times on the wire are timezone-aware UTC (`datetime.isoformat()`), so
storage, comparison, and conversion stay unambiguous.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.booking.models import Booking, Contact
from app.features.booking.schemas import (
    AvailabilityRequest,
    BookingCreate,
    ContactCreate,
    TimeSlot,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Source-of-truth for consultant working hours. Mirrors the persona which is
# Manila-based and books into Teams invites in the prospect's local time.
CONSULTANT_TIMEZONE = "Asia/Manila"

# Working day window (start, end) in consultant-local time, inclusive start,
# exclusive end.
WORKING_HOURS = (time(9, 0), time(17, 0))  # 09:00 - 17:00 Manila

# Length of each bookable slot.
SLOT_MINUTES = 30


def _resolve_tz(name: str | None) -> ZoneInfo:
    """Resolve an IANA tz name, falling back to UTC on bad input."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
async def get_or_create_contact(
    session: AsyncSession,
    *,
    email: str,
    full_name: str | None = None,
    phone: str | None = None,
    timezone_name: str | None = None,
    city: str | None = None,
) -> Contact:
    """Find a contact by email; create if missing. Updates mutable fields
    (name/phone/tz/city) if they are provided and differ from stored values."""
    stmt = select(Contact).where(Contact.email == email)
    result = await session.execute(stmt)
    contact = result.scalar_one_or_none()

    if contact is None:
        contact = Contact(
            full_name=full_name or email.split("@")[0],
            email=email,
            phone=phone,
            timezone=timezone_name,
            city=city,
        )
        session.add(contact)
        await session.flush()  # populate contact.id
        return contact

    # Update only non-None fields
    if full_name:
        contact.full_name = full_name
    if phone:
        contact.phone = phone
    if timezone_name:
        contact.timezone = timezone_name
    if city:
        contact.city = city
    return contact


async def create_contact(session: AsyncSession, payload: ContactCreate) -> Contact:
    """Create a contact from the ContactCreate schema (delegates to
    get_or_create so duplicate emails are idempotent)."""
    return await get_or_create_contact(
        session,
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        timezone_name=payload.timezone,
        city=payload.city,
    )


async def find_contact(
    session: AsyncSession, *,
    full_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> Contact | None:
    """Look up a contact by full_name, email, and/or phone.

    Backs the AI-caller tool `gja_contact_get`. At least one criterion is
    required. When multiple are given, any row matching ANY criterion is a
    candidate; ties are broken by preferring an email match, then a phone
    match, then a name match.
    """
    if not full_name and not email and not phone:
        return None
    stmt = select(Contact)
    clauses = []
    if email:
        clauses.append(Contact.email == email)
    if phone:
        clauses.append(Contact.phone == phone)
    if full_name:
        clauses.append(Contact.full_name == full_name)
    stmt = stmt.where(or_(*clauses))
    result = await session.execute(stmt)
    contacts = result.scalars().all()
    if not contacts:
        return None
    if len(contacts) == 1:
        return contacts[0]
    # Multiple matched (OR across criteria) — prefer email, then phone, then name.
    for c in contacts:
        if email and c.email == email:
            return c
    for c in contacts:
        if phone and c.phone == phone:
            return c
    for c in contacts:
        if full_name and c.full_name == full_name:
            return c
    return contacts[0]


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------
async def check_availability(
    session: AsyncSession, request: AvailabilityRequest
) -> list[TimeSlot]:
    """Compute free 30-min slots for the requested date (in requester's tz).

    Algorithm:
      1. Convert the requester's YYYY-MM-DD into the same calendar date in
         consultant-local time (Asia/Manila), so the slots offered reflect
         our consultant's working day for that requested day.
      2. Enumerate SLOT_MINUTES-wide windows from WORKING_HOURS start→end.
      3. Query confirmed bookings that overlap the consultant's working window.
      4. Drop slots overlapping any confirmed booking (or already in the past).
      5. Convert each surviving slot to the requester's tz for return.
    """
    req_tz = _resolve_tz(request.timezone)
    con_tz = ZoneInfo(CONSULTANT_TIMEZONE)

    # Build the consultant-local working window for the requested date.
    try:
        y, m, d = (int(x) for x in request.date.split("-"))
        day_in_consultant = datetime(y, m, d, tzinfo=con_tz)
    except (ValueError, TypeError):
        return []

    start_local = datetime.combine(day_in_consultant.date(), WORKING_HOURS[0], tzinfo=con_tz)
    end_local = datetime.combine(day_in_consultant.date(), WORKING_HOURS[1], tzinfo=con_tz)

    # Pull bookings whose window overlaps the working day. Pending bookings
    # also block slots so the availability view matches create_booking's
    # anti-double-book logic (which rejects pending + confirmed). Cancelled
    # and completed bookings are ignored so their slots free up again.
    overlap_stmt = (
        select(Booking)
        .where(Booking.status.in_(("pending", "confirmed")))
        .where(Booking.requested_at < end_local.astimezone(timezone.utc))
        .where(Booking.requested_at + timedelta(minutes=SLOT_MINUTES) > start_local.astimezone(timezone.utc))
    )
    result = await session.execute(overlap_stmt)
    busy = result.scalars().all()
    busy_intervals = [
        (
            b.requested_at.astimezone(timezone.utc),
            b.requested_at.astimezone(timezone.utc) + timedelta(minutes=b.duration_minutes),
        )
        for b in busy
    ]

    now_utc = datetime.now(timezone.utc)
    slots: list[TimeSlot] = []

    cursor = start_local
    while cursor + timedelta(minutes=SLOT_MINUTES) <= end_local:
        slot_start_utc = cursor.astimezone(timezone.utc)
        slot_end_utc = slot_start_utc + timedelta(minutes=SLOT_MINUTES)

        # Skip past slots.
        if slot_start_utc <= now_utc:
            cursor += timedelta(minutes=SLOT_MINUTES)
            continue

        # Drop if overlapping any confirmed booking.
        clash = any(
            slot_start_utc < busy_end and slot_end_utc > busy_start
            for busy_start, busy_end in busy_intervals
        )
        if not clash:
            slots.append(
                TimeSlot(
                    start=slot_start_utc.astimezone(req_tz),
                    end=slot_end_utc.astimezone(req_tz),
                )
            )
        cursor += timedelta(minutes=SLOT_MINUTES)

    return slots


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
async def create_booking(session: AsyncSession, payload: BookingCreate) -> Booking:
    """Create a booking. Requires either an existing contact_id OR enough info
    to create/fetch a contact (full_name + email).

    Validates time-zone awareness and checks against existing confirmed
    bookings to prevent double-booking before persisting.
    """
    # Resolve the requested_at to tz-aware UTC.
    requested_at = payload.requested_at
    if requested_at.tzinfo is None:
        # Treat naive input as the requester's tz (fallback UTC).
        requested_at = requested_at.replace(tzinfo=timezone.utc)
    requested_at_utc = requested_at.astimezone(timezone.utc)

    # Resolve contact.
    if payload.contact_id is not None:
        stmt = select(Contact).where(Contact.id == payload.contact_id)
        contact = (await session.execute(stmt)).scalar_one_or_none()
        if contact is None:
            raise ValueError(f"Contact {payload.contact_id} not found")
    else:
        if not payload.email or not payload.full_name:
            raise ValueError("booking requires either contact_id or (full_name + email)")
        contact = await get_or_create_contact(
            session,
            email=payload.email,
            full_name=payload.full_name,
            phone=payload.phone,
            timezone_name=payload.timezone,
            city=payload.city,
        )

    # Prevent double-booking against confirmed/pending bookings for the same slot.
    end_utc = requested_at_utc + timedelta(minutes=payload.duration_minutes)
    clash_stmt = (
        select(Booking)
        .where(Booking.status.in_(("confirmed", "pending")))
        .where(Booking.requested_at < end_utc)
        .where(Booking.requested_at + timedelta(minutes=SLOT_MINUTES) > requested_at_utc)
    )
    existing = (await session.execute(clash_stmt)).scalars().all()
    if existing:
        raise ValueError("Requested slot conflicts with an existing booking")

    booking = Booking(
        contact_id=contact.id,
        title=payload.title,
        requested_at=requested_at_utc,
        duration_minutes=payload.duration_minutes,
        status="pending",
        notes=payload.notes,
    )
    session.add(booking)
    await session.flush()
    # Eager-load contact so BookingRead.contact is populated on return.
    await session.refresh(booking, attribute_names=["contact"])
    return booking


async def list_bookings(session: AsyncSession, *, status_filter: str | None = None) -> list[Booking]:
    """List all bookings, optionally filtered by status, newest first."""
    stmt = select(Booking).options(selectinload(Booking.contact)).order_by(Booking.requested_at.desc())
    if status_filter:
        stmt = stmt.where(Booking.status == status_filter)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_booking(session: AsyncSession, booking_id: int) -> Booking | None:
    stmt = (
        select(Booking)
        .options(selectinload(Booking.contact))
        .where(Booking.id == booking_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_booking_status(
    session: AsyncSession, booking_id: int, new_status: str
) -> Booking | None:
    booking = await get_booking(session, booking_id)
    if booking is None:
        return None
    booking.status = new_status
    await session.flush()
    return booking
