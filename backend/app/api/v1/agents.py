"""Agents API router — /api/v1/agents"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
)

log = structlog.get_logger()
router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentListResponse:
    """List agents for the current organization (paginated)."""
    query = select(Agent).where(Agent.org_id == current_user.org_id)
    if status_filter:
        query = query.where(Agent.status == status_filter)

    # Total count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    # Paginated results
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Agent.created_at.desc())
    result = await db.execute(query)
    agents = result.scalars().all()

    return AgentListResponse(items=list(agents), total=total, page=page, page_size=page_size)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Agent:
    """Create a new agent. Defaults to Ollama llama3.2 provider."""
    agent = Agent(
        org_id=current_user.org_id,
        created_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    log.info("agent.created", agent_id=str(agent.id), name=agent.name)
    return agent


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Agent:
    """Get a single agent by ID."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == current_user.org_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Agent:
    """Partially update an agent."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == current_user.org_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)
    log.info("agent.updated", agent_id=str(agent_id))
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role("admin"),
) -> None:
    """Archive (soft-delete) an agent. Requires admin role."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == current_user.org_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    agent.status = "archived"
    await db.commit()
    log.info("agent.archived", agent_id=str(agent_id))
