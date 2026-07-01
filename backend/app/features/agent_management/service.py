"""Business logic for Agent + Tool management.

`assemble_settings()` here is the data-driven replacement for
`app.features.agent.settings.build_settings()` — it builds the same Deepgram
Settings dict but reads values from an Agent row (and the Agent's Tool rows).
The relay calls this instead of the hardcoded builder.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Config
from app.features.agent_management.models import Agent, Tool


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
async def list_tools(session: AsyncSession, *, active_only: bool = False) -> list[Tool]:
    stmt = select(Tool).order_by(Tool.name)
    if active_only:
        stmt = stmt.where(Tool.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def get_tool(session: AsyncSession, tool_id: int) -> Tool | None:
    return (await session.execute(select(Tool).where(Tool.id == tool_id))).scalar_one_or_none()


async def get_tool_by_name(session: AsyncSession, name: str) -> Tool | None:
    return (await session.execute(select(Tool).where(Tool.name == name))).scalar_one_or_none()


async def get_tools_by_ids(session: AsyncSession, ids: list[int]) -> list[Tool]:
    if not ids:
        return []
    stmt = select(Tool).where(Tool.id.in_(ids))
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
async def list_agents(session: AsyncSession, *, active_only: bool = False) -> list[Agent]:
    stmt = select(Agent).options(selectinload(Agent.tools)).order_by(Agent.id)
    if active_only:
        stmt = stmt.where(Agent.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def get_agent(session: AsyncSession, agent_id: int) -> Agent | None:
    stmt = select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.tools))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_agent_by_name(session: AsyncSession, name: str) -> Agent | None:
    stmt = select(Agent).where(Agent.name == name).options(selectinload(Agent.tools))
    return (await session.execute(stmt)).scalar_one_or_none()


async def assign_tools(session: AsyncSession, agent: Agent, tool_ids: list[int]) -> None:
    """Replace the agent's tool assignment with `tool_ids`."""
    tools = await get_tools_by_ids(session, tool_ids)
    # Eagerly load the current collection first. Without this, assigning to
    # `agent.tools` triggers a synchronous lazy-load to diff the association
    # table, which raises MissingGreenlet under asyncpg (and used to kill the
    # FastAPI lifespan startup before the server could bind its port).
    await session.refresh(agent, attribute_names=["tools"])
    agent.tools = tools
    await session.flush()


# ---------------------------------------------------------------------------
# Settings assembly (replaces settings.build_settings)
# ---------------------------------------------------------------------------

# These audio settings are universal for the managed Deepgram Voice Agent WS.
_AUDIO_SETTINGS = {
    "input": {"encoding": "linear16", "sample_rate": 24000},
    "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
}


def _tool_to_function_dict(tool: Tool) -> dict:
    """Convert a Tool ORM row to the Deepgram `{name, description, parameters}` shape."""
    # `parameters` may be JSONB-{} (empty) when the tool has no params.
    params = tool.parameters or {"type": "object", "properties": {}, "required": []}
    if isinstance(params, dict) and "type" not in params:
        params = {"type": "object", **params}
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": params,
    }


def assemble_settings(agent: Agent, *, tools: list[Tool] | None = None) -> dict:
    """Build the Deepgram Settings message from an Agent row.

    `tools` defaults to `agent.tools`; pass an override list for telemetry
    or to filter out inactive tools. Today we ship all the agent's tools.
    """
    tool_list = tools if tools is not None else agent.tools
    functions = [_tool_to_function_dict(t) for t in tool_list if t.is_active]

    return {
        "type": "Settings",
        "audio": _AUDIO_SETTINGS,
        "agent": {
            "listen": {
                "provider": {
                    "type": agent.stt_provider,
                    "model": agent.stt_model,
                    "smart_format": True,
                    "language": "en",
                }
            },
            "think": {
                "provider": {
                    "type": agent.llm_provider,
                    "model": agent.llm_model,
                    "temperature": agent.llm_temperature,
                },
                "endpoint": {
                    "url": "https://api.openai.com/v1/chat/completions",
                    "headers": {"authorization": f"Bearer {Config.OPENAI_API_KEY}"},
                },
                "prompt": agent.persona,
                "functions": functions,
            },
            "speak": {
                "provider": {"type": agent.tts_provider, "model": agent.tts_model},
            },
            "greeting": agent.greeting,
        },
    }
