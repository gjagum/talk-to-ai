"""SQLAlchemy models for Agent + Tool (the data-driven replacements for the
constants in `app/features/agent/settings.py`).

  - Agent : one AI Talking Agent. Holds the persona/greeting + per-agent
            STT/TTS/LLM model fields. Many-to-many with Tool.
  - Tool  : a callable the agent can invoke via Deepgram function-calling.
            LLM-facing contract (name/description/parameters) is editable in
            the dashboard; the actual implementation is referenced by
            `handler_key` and lives in `agent_management.handlers`.
  - agent_tools : M:N association.

`parameters` is stored as JSON (the Deepgram `{type, properties, required}`
schema) so we can ship it to Deepgram verbatim without a column-per-property.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


agent_tools = Table(
    "agent_tools",
    Base.metadata,
    Column("agent_id", ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    Column("tool_id", ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True),
)


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Deepgram function name (e.g. "gja_get_menu"). Must match what the LLM
    # emits in `FunctionCallRequest.functions[].name`.
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON-schema fragment shipped to Deepgram as `parameters`.
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Reference into HANDLERS in agent_management.handlers. Code owns the
    # impl; admin edits only the LLM-facing schema above.
    handler_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Persona (system prompt) and the spoken greeting.
    persona: Mapped[str] = mapped_column(Text, nullable=False)
    greeting: Mapped[str] = mapped_column(Text, nullable=False)

    # Per-agent pipeline model selections. Defaults reproduce today's behavior
    # (Deepgram nova-3 STT, OpenAI gpt-4o-mini think, Deepgram aura TTS).
    stt_provider: Mapped[str] = mapped_column(String(40), default="deepgram", nullable=False)
    stt_model: Mapped[str] = mapped_column(String(80), default="nova-3", nullable=False)
    tts_provider: Mapped[str] = mapped_column(String(40), default="deepgram", nullable=False)
    tts_model: Mapped[str] = mapped_column(String(80), default="aura-asteria-en", nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(40), default="open_ai", nullable=False)
    llm_model: Mapped[str] = mapped_column(String(80), default="gpt-4o-mini", nullable=False)
    llm_temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    tools: Mapped[list["Tool"]] = relationship(
        secondary=agent_tools, lazy="selectin"
    )
