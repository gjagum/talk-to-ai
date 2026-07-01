"""Admin CRUD endpoints for Agents, Tools, and support lookups.

All routes are permission-gated via `require_permission("<domain>:<action>")`.
They're mounted under `/api/admin` so the dashboard's auth requirement and the
public demo's lack thereof stay crisply separated by URL prefix.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.features.agent_management import service as am_service
from app.features.agent_management.handlers import list_handler_keys
from app.features.agent_management.models import Agent, Tool
from app.features.agent_management.schemas import (
    AgentCreate,
    AgentRead,
    AgentUpdate,
    HandlerKeyRead,
    ToolCreate,
    ToolRead,
    ToolUpdate,
)

router = APIRouter()


def _conflict_or_unprocessable(e: IntegrityError) -> HTTPException:
    detail = str(e.orig) if getattr(e, "orig", None) else "duplicate or invalid"
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@router.get("/tools/handler-keys", response_model=list[HandlerKeyRead])
async def handler_keys(_=Depends(require_permission("tool:read"))):
    return [HandlerKeyRead(key=k, label=v) for k, v in list_handler_keys()]


@router.get("/tools", response_model=list[ToolRead], dependencies=[Depends(require_permission("tool:read"))])
async def list_tools(session: AsyncSession = Depends(get_db)):
    return await am_service.list_tools(session)


@router.post(
    "/tools",
    response_model=ToolRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("tool:create"))],
)
async def create_tool(payload: ToolCreate, session: AsyncSession = Depends(get_db)):
    tool = Tool(
        name=payload.name,
        description=payload.description,
        parameters=payload.parameters,
        handler_key=payload.handler_key,
        is_active=payload.is_active,
    )
    session.add(tool)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise _conflict_or_unprocessable(e)
    await session.refresh(tool)
    return tool


@router.put(
    "/tools/{tool_id}",
    response_model=ToolRead,
    dependencies=[Depends(require_permission("tool:update"))],
)
async def update_tool(tool_id: int, payload: ToolUpdate, session: AsyncSession = Depends(get_db)):
    tool = await am_service.get_tool(session, tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(tool, key, value)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise _conflict_or_unprocessable(e)
    await session.refresh(tool)
    return tool


@router.delete(
    "/tools/{tool_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("tool:delete"))],
)
async def delete_tool(tool_id: int, session: AsyncSession = Depends(get_db)):
    tool = await am_service.get_tool(session, tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    await session.delete(tool)
    await session.commit()


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
@router.get(
    "/agents",
    response_model=list[AgentRead],
    dependencies=[Depends(require_permission("agent:read"))],
)
async def list_agents(session: AsyncSession = Depends(get_db)):
    return await am_service.list_agents(session)


@router.get(
    "/agents/{agent_id}",
    response_model=AgentRead,
    dependencies=[Depends(require_permission("agent:read"))],
)
async def get_agent(agent_id: int, session: AsyncSession = Depends(get_db)):
    agent = await am_service.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post(
    "/agents",
    response_model=AgentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("agent:create"))],
)
async def create_agent(payload: AgentCreate, session: AsyncSession = Depends(get_db)):
    agent = Agent(
        name=payload.name,
        description=payload.description,
        persona=payload.persona,
        greeting=payload.greeting,
        stt_provider=payload.stt_provider,
        stt_model=payload.stt_model,
        tts_provider=payload.tts_provider,
        tts_model=payload.tts_model,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
        llm_temperature=payload.llm_temperature,
        is_active=payload.is_active,
    )
    session.add(agent)
    await session.flush()
    await am_service.assign_tools(session, agent, payload.tool_ids)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise _conflict_or_unprocessable(e)
    await session.refresh(agent)
    return agent


@router.put(
    "/agents/{agent_id}",
    response_model=AgentRead,
    dependencies=[Depends(require_permission("agent:update"))],
)
async def update_agent(agent_id: int, payload: AgentUpdate, session: AsyncSession = Depends(get_db)):
    agent = await am_service.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    data = payload.model_dump(exclude_unset=True)
    tool_ids = data.pop("tool_ids", None)
    for key, value in data.items():
        setattr(agent, key, value)
    if tool_ids is not None:
        await am_service.assign_tools(session, agent, tool_ids)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise _conflict_or_unprocessable(e)
    await session.refresh(agent)
    return agent


@router.delete(
    "/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("agent:delete"))],
)
async def delete_agent(agent_id: int, session: AsyncSession = Depends(get_db)):
    agent = await am_service.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await session.delete(agent)
    await session.commit()
