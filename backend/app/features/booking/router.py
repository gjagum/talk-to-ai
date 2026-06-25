"""REST endpoints for the booking domain.

Endpoints double as the AI-caller tool surface (documented inline so the later
agent-function-loop wiring is mechanical):

  POST /contacts            create a contact
  GET  /contacts            (gja_contact_get)     ?email=&phone=
  GET  /availability        (gja_check_availability)  ?date=YYYY-MM-DD&timezone=...
  GET  /                    list bookings (UI + admin)
  POST /                    (gja_create_event)    create a booking
  GET  /{booking_id}        fetch one booking
  PATCH /{booking_id}/status   update status (pending|confirmed|cancelled|completed)

All write endpoints commit their session. Inputs/outputs are validated by the
Pydantic schemas in schemas.py.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.booking import service
from app.features.booking.schemas import (
    AvailabilityRequest,
    AvailabilityResponse,
    BookingCreate,
    BookingRead,
    BookingStatusUpdate,
    ContactCreate,
    ContactRead,
    TimeSlot,
)
from app.features.booking.service import CONSULTANT_TIMEZONE

router = APIRouter()


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
@router.post("/contacts", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
async def create_contact(payload: ContactCreate, session: AsyncSession = Depends(get_db)):
    """Create (or upsert by email) a contact."""
    contact = await service.create_contact(session, payload)
    await session.commit()
    await session.refresh(contact)
    return contact


@router.get("/contacts", response_model=list[ContactRead])
async def get_contact(
    email: str | None = Query(default=None, description="Email to look up"),
    phone: str | None = Query(default=None, description="Phone to look up"),
    session: AsyncSession = Depends(get_db),
):
    """(AI tool: gja_contact_get) Find a contact by email and/or phone."""
    contact = await service.find_contact(session, email=email, phone=phone)
    return [contact] if contact else []


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------
@router.get("/availability", response_model=AvailabilityResponse)
async def check_availability(
    date: str = Query(..., description="YYYY-MM-DD in requester's local tz"),
    timezone: str = Query("UTC", description="IANA tz of the requester"),
    session: AsyncSession = Depends(get_db),
):
    """(AI tool: gja_check_availability) Free 30-min slots for `date`,
    computed in consultant time and returned in the requester's timezone."""
    request = AvailabilityRequest(date=date, timezone=timezone)
    slots = await service.check_availability(session, request)
    return AvailabilityResponse(
        date=date,
        timezone=timezone,
        consultant_timezone=CONSULTANT_TIMEZONE,
        slots=slots,
    )


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[BookingRead])
async def list_bookings(
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db),
):
    """List all bookings, optionally filtered by status, newest first."""
    return await service.list_bookings(session, status_filter=status_filter)


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(payload: BookingCreate, session: AsyncSession = Depends(get_db)):
    """(AI tool: gja_create_event) Book a slot for a contact."""
    try:
        booking = await service.create_booking(session, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await session.commit()
    await session.refresh(booking, attribute_names=["contact"])
    return booking


@router.get("/{booking_id}", response_model=BookingRead)
async def get_booking(booking_id: int, session: AsyncSession = Depends(get_db)):
    booking = await service.get_booking(session, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.patch("/{booking_id}/status", response_model=BookingRead)
async def update_booking_status(
    booking_id: int,
    payload: BookingStatusUpdate,
    session: AsyncSession = Depends(get_db),
):
    booking = await service.update_booking_status(session, booking_id, payload.status)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    await session.commit()
    await session.refresh(booking, attribute_names=["contact"])
    return booking
