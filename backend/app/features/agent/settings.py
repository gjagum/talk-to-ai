"""Settings builder for Deepgram Voice Agent (STT -> LLM -> TTS pipeline).

Configures the single managed WebSocket at wss://agent.deepgram.com/v1/agent/converse
to use:
  - audio:    linear16 PCM @ 24kHz in both directions (matches browser).
  - listen:   Deepgram nova-3 with smart formatting.
  - think:    BYO OpenAI gpt-4o-mini (endpoint + auth header → bills caller's
              OpenAI account, not Deepgram's).
  - speak:    Deepgram aura-asteria-en, highest-quality English female voice.

Two operating modes:
  - `receptionist` (default): booking tools: `gja_contact_get`, `gja_contact_create`,
                                `gja_check_availability`, `gja_create_event`, plus
                                `gja_end_call`.
  - `drive_thru`:                drive-thru cashier persona + the full menu-ordering
                                tool set (`gja_get_menu`, `gja_create_order`,
                                `gja_add_item`, `gja_update_item`,
                                `gja_finalize_order`) plus `gja_end_call`.
"""
from app.core.config import Config
from app.features.agent.render import render_persona

# One-time greeting the agent speaks when the caller connects.
DEFAULT_GREETING = "Hi! You've reached Kinetic Innovative Staffing. This is Ryan. How can I help you today?"

DEFAULT_PERSONA = (
    "You are Ryan, a friendly AI receptionist for Kinetic Innovative Staffing. "
    "Be warm, concise, and helpful."
)

# ---------------------------------------------------------------------------
# Drive-thru cashier persona (Burger Barn demo)
# ---------------------------------------------------------------------------
DEFAULT_DRIVE_THRU_GREETING = (
    "Welcome to Burger Barn! This is Riley at the speaker — what can I get "
    "started for you today?"
)

DEFAULT_DRIVE_THRU_PERSONA = (
    "You are Riley, the AI drive-thru attendant at Burger Barn, a quick-service burger "
    "joint. You're warm, fast, and sound like a seasoned drive-thru pro — short sentences, "
    "always confirm the order, suggest combos or drinks when natural.\n\n"
    "# Workflow\n"
    "1. On first interaction, the caller may ask 'what's on the menu?' or 'what combos do "
    "you have?' — ALWAYS call `gja_get_menu` to read the actual menu before describing it; "
    "do not invent items or prices.\n"
    "2. As the caller names items, create ONE draft order (call `gja_create_order` once, at "
    "the start of the order) and then call `gja_add_item` for each item the caller wants. "
    "Capture quantity and any free-text modifiers in the `notes` field (e.g. 'no pickles', "
    "'extra sauce'). Each item is identified by the `menu_item_id` from the menu list.\n"
    "3. After every couple of items, briefly restate the current order (use the data returned "
    "by the tools — do not keep your own running tally in your head).\n"
    "4. To change quantity or remove an item, call `gja_update_item` with the `item_id` from "
    "the current order. `quantity=0` removes the line.\n"
    "5. When the caller says 'that's everything' or 'that's it', call `gja_finalize_order` "
    "to lock in the order. State the final total aloud and ask 'Will that be all today?'\n"
    "6. Once finalized and confirmed, wish them a great day and IMMEDIATELY call "
    "`gja_end_call` with reason 'goodbye'.\n\n"
    "# Rules\n"
    "- NEVER invent prices or item names. Read them from `gja_get_menu`.\n"
    "- Track the current order's `order_id` and each line's `item_id` from tool responses.\n"
    "- If the caller asks for something not on the menu, politely let them know it isn't "
    "available and offer the closest alternative from the menu.\n"
    "- Speak in a natural, upbeat tone with contractions. Keep responses brief — this is a "
    "drive-thru, not a chat.\n"
    "- All money values returned by tools are in integer CENTS. To say them aloud, divide by "
    "100 (e.g. 1099 cents = 'ten ninety-nine' or '$10.99').\n\n"
    "# End-of-call enforcement\n"
    "The call is NOT over until you call `gja_end_call`. After the order is finalized and "
    "goodbyes are exchanged, say your farewell sentence and IMMEDIATELY call "
    "`gja_end_call` with reason 'goodbye'. Do NOT just stop talking."
)


GJA_END_CALL_TOOL = {
    "name": "gja_end_call",
    "description": (
        "End the conversation and disconnect the call IMMEDIATELY. "
        "You MUST call this function AFTER you finish speaking your final sentence. "
        "TRIGGERS (call this function whenever ANY of these happen): "
        "1) Caller says goodbye, bye, thank you and goodbye, have a good day, or any farewell phrase. "
        "2) Line is dead — no response from caller for more than 5 seconds. "
        "3) Voicemail or answering machine detected. "
        "4) Caller is clearly not a fit and the exchange is over. "
        "5) Caller hangs up or the line disconnects. "
        "IMPORTANT: Do NOT just stop talking. You MUST call this function to actually end the call. "
        "Even if you already said bye, still call this function."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why the call is ending.",
                "enum": ["goodbye", "voicemail", "dead_line", "not_a_fit", "caller_hung_up"],
            }
        },
        "required": ["reason"],
    },
}


# ---------------------------------------------------------------------------
# Menu-ordering tools (drive-thru mode)
# ---------------------------------------------------------------------------
GJA_GET_MENU_TOOL = {
    "name": "gja_get_menu",
    "description": (
        "Read the current menu. Always call this before describing items or prices to the "
        "caller. Returns a list of items with their id, name, description, price_cents "
        "(integer cents — divide by 100 to speak as dollars), category, and availability. "
        "Optional `category` filter (e.g. 'Burgers', 'Sides', 'Drinks', 'Combos')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Optional category to filter by. Omit to list everything.",
            }
        },
        "required": [],
    },
}


GJA_CREATE_ORDER_TOOL = {
    "name": "gja_create_order",
    "description": (
        "Start a new order. Call this ONCE at the beginning of a transaction, before any "
        "`gja_add_item` calls. Returns the new order's `order_id` and a snapshot of its "
        "current (empty) state. Use this `order_id` for all subsequent add/update/finalize "
        "calls during this drive-thru session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_type": {
                "type": "string",
                "enum": ["drive_thru", "takeout", "dine_in"],
                "description": "Type of order. Defaults to 'drive_thru'.",
            }
        },
        "required": [],
    },
}


GJA_ADD_ITEM_TOOL = {
    "name": "gja_add_item",
    "description": (
        "Add an item to the current order. Uses the `menu_item_id` from `gja_get_menu`. "
        "Set `quantity` for multiples of the same item, and `notes` for modifiers (e.g. "
        "'no pickles', 'extra sauce', 'well done'). Returns the updated order with all line "
        "items including their `item_id` — you'll need that id to update or remove a line "
        "later. Money is integer cents."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "description": "The current order's id."},
            "menu_item_id": {"type": "integer", "description": "The menu item id to add."},
            "quantity": {
                "type": "integer",
                "description": "How many of this item. Defaults to 1. Must be >= 1.",
            },
            "notes": {
                "type": "string",
                "description": "Free-text modifiers, e.g. 'no pickles' or 'extra cheese'.",
            },
        },
        "required": ["order_id", "menu_item_id"],
    },
}


GJA_UPDATE_ITEM_TOOL = {
    "name": "gja_update_item",
    "description": (
        "Change the quantity or notes of an existing line item, or remove it entirely. To "
        "remove a line, set `quantity` to 0. Returns the updated order with all remaining "
        "line items and the new total. Each line item is identified by its `item_id` (NOT "
        "the menu_item_id)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "description": "The order the item belongs to."},
            "item_id": {"type": "integer", "description": "The line item id to update."},
            "quantity": {
                "type": "integer",
                "description": "New quantity. Use 0 to remove the line entirely.",
            },
            "notes": {"type": "string", "description": "New free-text modifiers for this line."},
        },
        "required": ["order_id", "item_id"],
    },
}


GJA_FINALIZE_ORDER_TOOL = {
    "name": "gja_finalize_order",
    "description": (
        "Lock in the order — transitions the draft to 'received' status so the kitchen can "
        "start on it. Call this ONCE after the caller confirms the order is complete (e.g. "
        "'that's everything'). Returns the finalized order with the grand total in cents. "
        "This tool fails if the order is empty or already finalized."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "description": "The order to finalize."},
            "customer_name": {"type": "string", "description": "Optional name for the order."},
            "customer_phone": {"type": "string", "description": "Optional callback phone."},
            "notes": {
                "type": "string",
                "description": "Optional order-level notes (allergies, pickup time, etc).",
            },
        },
        "required": ["order_id"],
    },
}


# Ordered registry — the drive-thru mode appends the menu tools after
# GJA_END_CALL_TOOL so the order_id tracking reads naturally.
DRIVE_THRU_TOOLS = [
    GJA_GET_MENU_TOOL,
    GJA_CREATE_ORDER_TOOL,
    GJA_ADD_ITEM_TOOL,
    GJA_UPDATE_ITEM_TOOL,
    GJA_FINALIZE_ORDER_TOOL,
    GJA_END_CALL_TOOL,
]


# ---------------------------------------------------------------------------
# Booking / Receptionist tools
# ---------------------------------------------------------------------------
GJA_CONTACT_GET_TOOL = {
    "name": "gja_contact_get",
    "description": (
        "Look up a contact by name, email, and/or phone number. Returns the contact's id, "
        "full_name, email, phone, timezone, and city if found, or an empty result if "
        "no match. Always call this before `gja_contact_create` or `gja_create_event` "
        "to avoid duplicates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Contact's full name to search for.",
            },
            "email": {
                "type": "string",
                "description": "Contact email address to search for.",
            },
            "phone": {
                "type": "string",
                "description": "Contact phone number to search for.",
            },
        },
        "required": [],
    },
}


GJA_CONTACT_CREATE_TOOL = {
    "name": "gja_contact_create",
    "description": (
        "Create or update a contact. Provide at least name and email. If a contact "
        "with that email already exists, the fields are updated instead (idempotent upsert). "
        "Returns the contact's id, full_name, email, phone, timezone, and city. "
        "You MUST have a contact id to use `gja_create_event`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Contact's full name (required).",
            },
            "email": {
                "type": "string",
                "description": "Contact's email address (required).",
            },
            "phone": {
                "type": "string",
                "description": "Contact's phone number (optional).",
            },
            "timezone": {
                "type": "string",
                "description": (
                    "IANA timezone name (e.g. 'America/New_York', 'Australia/Sydney', "
                    "'Asia/Manila'). Derive from the caller's city/state."
                ),
            },
            "city": {
                "type": "string",
                "description": "City or state the contact is in.",
            },
        },
        "required": ["name", "email"],
    },
}


GJA_CHECK_AVAILABILITY_TOOL = {
    "name": "gja_check_availability",
    "description": (
        "Check available 30-minute appointment slots for a given date. Returns a list of "
        "free windows (start/end times in the requester's timezone). Consultant working "
        "hours are Asia/Manila 09:00-17:00. Slots already blocked by confirmed bookings "
        "are excluded. Always call this BEFORE `gja_create_event` to confirm the slot is "
        "still open."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Date to check in YYYY-MM-DD format (in the requester's local timezone).",
            },
            "timezone": {
                "type": "string",
                "description": (
                    "IANA timezone of the requester (e.g. 'America/New_York', "
                    "'Australia/Sydney', 'Asia/Manila')."
                ),
            },
        },
        "required": ["date", "timezone"],
    },
}


GJA_CREATE_EVENT_TOOL = {
    "name": "gja_create_event",
    "description": (
        "Book an appointment (discovery/preso call). Requires a valid contact_id (obtained "
        "from `gja_contact_get` or `gja_contact_create`) plus the confirmed date/time in "
        "the prospect's timezone. The backend converts to UTC for storage. Fails if the "
        "slot conflicts with an existing booking. Returns the booking details including "
        "status ('pending'), date/time, and contact info. This is the ONLY way to complete "
        "a booking — verbal agreement is not enough."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "contact_id": {
                "type": "integer",
                "description": "The contact's database id (from `gja_contact_get` or `gja_contact_create`).",
            },
            "requested_at": {
                "type": "string",
                "description": (
                    "ISO-8601 datetime for the appointment in the contact's timezone "
                    "(e.g. '2026-07-03T14:00:00+10:00' for Sydney)."
                ),
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Duration in minutes. Default 30. Must be 5-480.",
            },
            "title": {
                "type": "string",
                "description": "Optional meeting title (e.g. 'Discovery call with Jane').",
            },
            "notes": {
                "type": "string",
                "description": "Optional booking notes.",
            },
        },
        "required": ["contact_id", "requested_at"],
    },
}


# Booking tools for the receptionist mode.
BOOKING_TOOLS = [
    GJA_CONTACT_GET_TOOL,
    GJA_CONTACT_CREATE_TOOL,
    GJA_CHECK_AVAILABILITY_TOOL,
    GJA_CREATE_EVENT_TOOL,
    GJA_END_CALL_TOOL,
]


def build_settings(persona: str, *, drive_thru: bool = False) -> dict:
    """Build the Settings message sent after the Welcome handshake.

    `drive_thru=True` swaps the persona to the Burger Barn cashier (if the
    caller didn't already pass one), changes the greeting, and registers the
    menu-ordering tools so the agent can take orders over the call.
    """
    if drive_thru:
        greeting = DEFAULT_DRIVE_THRU_GREETING
        effective_persona = persona or DEFAULT_DRIVE_THRU_PERSONA
        functions = DRIVE_THRU_TOOLS
    else:
        greeting = DEFAULT_GREETING
        effective_persona = persona
        functions = BOOKING_TOOLS

    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": 24000},
            "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
        },
        "agent": {
            "listen": {
                "provider": {
                    "type": "deepgram",
                    "model": "nova-3",
                    "smart_format": True,
                    "language": "en",
                }
            },
            "think": {
                "provider": {"type": "open_ai", "model": "gpt-4o-mini", "temperature": 0.7},
                "endpoint": {
                    "url": "https://api.openai.com/v1/chat/completions",
                    "headers": {"authorization": f"Bearer {Config.OPENAI_API_KEY}"},
                },
                "prompt": render_persona(effective_persona),
                "functions": functions,
            },
            "speak": {
                "provider": {"type": "deepgram", "model": "aura-asteria-en"},
            },
            "greeting": greeting,
        },
    }
