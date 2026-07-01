"""Pydantic schemas for the agent_management domain.

Note on `parameters` (Tool): it's a free-form JSON object — the Deepgram
`{type, properties, required}` schema. The validator guards against egregious
shapes (must be a dict-like with `type == "object"` or empty) but the dashboard
form edits it as raw JSON.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
class ToolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    parameters: dict[str, Any]
    handler_key: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    handler_key: str = Field(..., min_length=1, max_length=120)
    is_active: bool = True


class ToolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    parameters: dict[str, Any] | None = None
    handler_key: str | None = None
    is_active: bool | None = None


class HandlerKeyRead(BaseModel):
    """Lists the handler keys the registry knows about, so the Tools form can
    render a dropdown instead of free text."""

    key: str
    label: str


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    persona: str
    greeting: str
    stt_provider: str
    stt_model: str
    tts_provider: str
    tts_model: str
    llm_provider: str
    llm_model: str
    llm_temperature: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
    tools: list[ToolRead] = []


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    persona: str
    greeting: str
    stt_provider: str = "deepgram"
    stt_model: str = "nova-3"
    tts_provider: str = "deepgram"
    tts_model: str = "aura-asteria-en"
    llm_provider: str = "open_ai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    is_active: bool = True
    tool_ids: list[int] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    persona: str | None = None
    greeting: str | None = None
    stt_provider: str | None = None
    stt_model: str | None = None
    tts_provider: str | None = None
    tts_model: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_temperature: float | None = None
    is_active: bool | None = None
    tool_ids: list[int] | None = None  # if provided, replaces the assignment set
