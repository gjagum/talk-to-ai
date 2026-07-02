"""Resolve unrendered Liquid-style placeholders in agent persona prompts.

The personas shipped to the relay (see ``frontend/src/lib/personas.js``) embed
date/time tags such as ``{{ "now" | date: "%B %d, %Y", "Asia/Manila"}}`` and
caller-variable tags like ``{{name}}``, ``{{email}}``. No templating engine is
wired into the relay path, so these tags would otherwise reach the LLM verbatim
— leaving the model with no real date anchor and causing it to hallucinate past
dates when checking availability. We resolve the date/time tags server-side
before the prompt is sent to Deepgram, and optionally resolve ``{{name}}`` /
``{{email}}`` when caller context is available.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

# Exact placeholder strings as authored in personas.js. ``str.replace`` needs a
# byte-for-byte match, so these are kept literal rather than reconstructed.
_DATE_TAG = '{{ "now" | date: "%B %d, %Y", "Asia/Manila"}}'
_TIME_TAG = '{{ "now" | date: "%I:%M %p", "Asia/Manila"}}'
_NAME_TAG = "{{name}}"
_EMAIL_TAG = "{{email}}"
_PHONE_TAG = "{{phone}}"


def render_persona(
    persona: str | None,
    *,
    tz: str = "Asia/Manila",
    name: str = "",
    email: str = "",
    phone: str = "",
) -> str:
    """Replace date/time tags and optional caller variables in a persona string.

    ``{{ "now" | date: "%B %d, %Y", "Asia/Manila"}}`` and
    ``{{ "now" | date: "%I:%M %p", "Asia/Manila"}}`` are always resolved to
    the server's current time.

    ``{{name}}``, ``{{email}}``, and ``{{phone}}`` are resolved **only** when a
    non-empty value is supplied via the corresponding parameter. When omitted
    (or empty) these placeholders are left untouched so the LLM can handle them
    dynamically.

    A falsy/empty ``persona`` returns an empty string.
    """
    if not persona:
        return ""
    now = datetime.now(ZoneInfo(tz))
    resolved = persona.replace(_DATE_TAG, now.strftime("%B %d, %Y")).replace(
        _TIME_TAG, now.strftime("%I:%M %p")
    )
    if name:
        resolved = resolved.replace(_NAME_TAG, name)
    if email:
        resolved = resolved.replace(_EMAIL_TAG, email)
    if phone:
        resolved = resolved.replace(_PHONE_TAG, phone)
    return resolved
