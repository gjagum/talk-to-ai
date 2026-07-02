"""Tests for app.features.agent.render.render_persona.

These pin the behavior of the date/time placeholder resolver that runs on the
relay path before a persona is sent to Deepgram: the two ``{{ "now" | date }}``
Liquid tags must resolve to a real server date/time (Asia/Manila), while any
other ``{{...}}`` placeholder is left untouched (its resolution requires caller
context the relay does not have today).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.features.agent.render import render_persona

# Exact placeholder strings as authored in frontend/src/lib/personas.js.
DATE_TAG = '{{ "now" | date: "%B %d, %Y", "Asia/Manila"}}'
TIME_TAG = '{{ "now" | date: "%I:%M %p", "Asia/Manila"}}'

MANILA = ZoneInfo("Asia/Manila")


def test_replaces_date_tag_with_formatted_manila_date():
    out = render_persona(f"Today is {DATE_TAG}.")
    expected = datetime.now(MANILA).strftime("%B %d, %Y")
    assert out == f"Today is {expected}."


def test_replaces_time_tag_with_formatted_manila_time():
    out = render_persona(f"It is {TIME_TAG} now.")
    expected = datetime.now(MANILA).strftime("%I:%M %p")
    assert out == f"It is {expected} now."


def test_replaces_both_tags_together():
    out = render_persona(f"{DATE_TAG} {TIME_TAG}")
    now = datetime.now(MANILA)
    expected = f"{now.strftime('%B %d, %Y')} {now.strftime('%I:%M %p')}"
    assert out == expected


def test_leaves_unknown_placeholders_untouched():
    # email/name/phone cannot be resolved without caller context; they must be
    # passed through verbatim rather than dropped. Built as a plain string (not
    # an f-string) so the literal braces survive.
    src = DATE_TAG + " keep {{email}} {{name}} {{nested}}"
    out = render_persona(src)
    assert "{{email}}" in out
    assert "{{name}}" in out
    assert "{{nested}}" in out
    assert DATE_TAG not in out


def test_empty_string_returns_empty_string():
    assert render_persona("") == ""


def test_none_returns_empty_string():
    assert render_persona(None) == ""


def test_no_tags_returned_unchanged():
    src = "A persona with no placeholders at all."
    assert render_persona(src) == src


def test_result_uses_asia_manila_timezone():
    # The resolved date must match Manila, not the server's local tz. We can't
    # assert exact equality with "now" across a boundary, so we assert the
    # rendered date matches a fresh Manila computation.
    out = render_persona(DATE_TAG)
    assert out == datetime.now(MANILA).strftime("%B %d, %Y")


def test_custom_timezone_argument():
    # ``tz`` kwarg should steer the resolution. Use a tag-free check by
    # rendering the date tag and comparing against Sydney.
    sydney = ZoneInfo("Australia/Sydney")
    out = render_persona(DATE_TAG, tz="Australia/Sydney")
    assert out == datetime.now(sydney).strftime("%B %d, %Y")
    # And it should differ from Manila when the two zones are on different
    # calendar days (true on most, but not all, days — so only assert equality
    # to the Sydney value, which is always correct).
