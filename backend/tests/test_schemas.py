"""Tests for app.features.booking.schemas.

Covers the read-side email coercion specifically: a malformed email stored on a
Contact (e.g. a legacy unrendered `{{email}}` placeholder written by the agent
before input-field resolution was wired) must not 500 the bookings list. We
swap it for a placeholder on read. Writes stay strict (ContactCreate / EmailStr).
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.features.booking.schemas import ContactCreate, ContactRead


def _contact_kwargs(**overrides):
    base = dict(
        id=1,
        full_name="Caller",
        email="caller@example.com",
        phone=None,
        timezone=None,
        city=None,
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return base


def test_contact_read_accepts_valid_email():
    c = ContactRead(**_contact_kwargs(email="jane@example.com"))
    assert c.email == "jane@example.com"


def test_contact_read_coerces_placeholder_email():
    # Legacy row: agent stored the literal `{{email}}` placeholder. Reading it
    # must not raise — it should fall back to a placeholder string.
    c = ContactRead(**_contact_kwargs(email="{{email}}"))
    assert c.email == "(invalid)"


def test_contact_read_coerces_email_without_at_sign():
    c = ContactRead(**_contact_kwargs(email="not-an-email"))
    assert c.email == "(invalid)"


def test_contact_read_coerces_none_email():
    # ORM column is non-nullable in practice, but be defensive on read.
    c = ContactRead(**_contact_kwargs(email=None))
    assert c.email == "(invalid)"


def test_contact_create_still_rejects_bad_email():
    # Writes remain strict — the coercion is read-side only.
    with pytest.raises(ValidationError):
        ContactCreate(full_name="Caller", email="{{email}}")
    with pytest.raises(ValidationError):
        ContactCreate(full_name="Caller", email="not-an-email")


def test_contact_create_accepts_valid_email():
    c = ContactCreate(full_name="Caller", email="jane@example.com")
    assert c.email == "jane@example.com"
