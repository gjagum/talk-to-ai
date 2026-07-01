"""Public persona read/write endpoints for the voice-demo pages.

The Management dashboard (under `/api/admin`, permission-gated) is the
canonical editor for Agents, but the persona prompt is also useful to tweak
inline from the demo pages themselves (Home / Drive-Thru) without forcing a
sign-in. This tiny public surface exposes ONLY the persona text for the two
canonical demo agents, so an unauthenticated visitor can:

  GET  /api/agents/{name}/persona          → {persona | null}
  PUT  /api/agents/{name}/persona          body {persona} → {persona}

`{name}` is restricted to an allowlist (receptionist, drive_thru) — anything
else 404s. Returning `null` for GET tells the frontend to fall back to its
hardcoded default (people still get a working demo even with an empty DB or
before the seeder has run).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.agent_management import service as am_service

router = APIRouter()

# Only the canonical seeded personas are exposed publicly. Anything else is a
# 404 so this surface can't be used to enumerate or poke at other agents.
_PUBLIC_PERSONA_AGENTS = frozenset({"receptionist", "drive_thru"})


class PersonaRead(BaseModel):
    """`persona` is None when the agent doesn't exist yet or has no persona —
    the frontend then falls back to its hardcoded default."""

    name: str
    persona: str | None = None


class PersonaWrite(BaseModel):
    persona: str


def _check_name(name: str) -> None:
    if name not in _PUBLIC_PERSONA_AGENTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown agent")


@router.get("/agents/{name}/persona", response_model=PersonaRead)
async def get_persona(name: str, session: AsyncSession = Depends(get_db)):
    """Public: read the saved persona (or null → use the hardcoded default)."""
    _check_name(name)
    persona = await am_service.get_persona_by_name(session, name)
    return PersonaRead(name=name, persona=persona)


@router.put("/agents/{name}/persona", response_model=PersonaRead)
async def put_persona(
    name: str, payload: PersonaWrite, session: AsyncSession = Depends(get_db)
):
    """Public: save the persona. Requires the agent to already exist
    (the seeder runs at startup, so this is the normal case)."""
    _check_name(name)
    persona = (payload.persona or "").strip()
    agent = await am_service.set_persona_by_name(session, name, persona)
    if agent is None:
        # Agent row is missing entirely — seed hasn't run or was deleted.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not seeded yet; persona cannot be saved.",
        )
    await session.commit()
    return PersonaRead(name=name, persona=agent.persona)
