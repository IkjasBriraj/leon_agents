"""Runs API router — /api/v1/runs"""

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.models.run import Run
from app.models.user import User
from app.schemas.run import (
    RunCreate,
    RunListResponse,
    RunResponse,
    RunResumePayload,
)

log = structlog.get_logger()
router = APIRouter(prefix="/runs", tags=["Runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> Run:
    """
    Start a new agent workflow run.

    Creates the Run record immediately (status=pending) and dispatches
    execution as a background task. The run_id is returned instantly.
    Track progress via the WebSocket endpoint: WS /api/v1/ws/runs/{run_id}
    """
    # Create the Run record
    run = Run(
        org_id=current_user.org_id,
        workflow_id=payload.workflow_id,
        triggered_by=current_user.id,
        input_data=payload.input_data,
        status="pending",
        metadata_=payload.metadata,
    )
    from sqlalchemy.orm.attributes import set_committed_value
    db.add(run)
    await db.commit()
    await db.refresh(run)
    set_committed_value(run, "steps", [])

    # Enqueue to Redis Streams for the engine worker to pick up
    await redis.xadd(
        "agentcraft:run_queue",
        {
            "run_id": str(run.id),
            "workflow_id": str(payload.workflow_id),
            "org_id": str(current_user.org_id),
            "user_id": str(current_user.id),
        },
    )

    log.info("run.enqueued", run_id=str(run.id), workflow_id=str(payload.workflow_id))
    return run


@router.get("", response_model=RunListResponse)
async def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    workflow_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunListResponse:
    """List runs for the current organization (paginated, filterable)."""
    query = select(Run).where(Run.org_id == current_user.org_id)
    if status_filter:
        query = query.where(Run.status == status_filter)
    if workflow_id:
        query = query.where(Run.workflow_id == workflow_id)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Run.created_at.desc())
    result = await db.execute(query)
    runs = result.scalars().all()

    return RunListResponse(items=list(runs), total=total, page=page, page_size=page_size)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Run:
    """Get a run with all its execution steps."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Run)
        .where(Run.id == run_id, Run.org_id == current_user.org_id)
        .options(selectinload(Run.steps))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.post("/{run_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Cancel a running or pending execution."""
    result = await db.execute(
        select(Run).where(Run.id == run_id, Run.org_id == current_user.org_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status not in ("pending", "running", "paused_hitl"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel run with status '{run.status}'",
        )

    # Signal the engine to cancel via Redis
    await redis.set(f"agentcraft:cancel:{run_id}", "1", ex=3600)
    run.status = "cancelled"
    await db.commit()

    log.info("run.cancelled", run_id=str(run_id))
    return {"status": "cancelled", "run_id": str(run_id)}


@router.post("/{run_id}/resume", status_code=status.HTTP_200_OK)
async def resume_run(
    run_id: uuid.UUID,
    payload: RunResumePayload,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Resume a HITL-paused run with a human decision (approve/reject).

    The human can also supply `edited_state` to modify intermediate
    agent state before resuming — enabling mid-run steering.
    """
    result = await db.execute(
        select(Run).where(Run.id == run_id, Run.org_id == current_user.org_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "paused_hitl":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not paused for human approval",
        )

    import json

    # Push resume decision to Redis for the engine to pick up
    await redis.lpush(
        f"agentcraft:hitl_resume:{run_id}",
        json.dumps({
            "decision": payload.decision,
            "edited_state": payload.edited_state,
            "message": payload.message,
            "approved_by": str(current_user.id),
        }),
    )

    log.info("run.hitl_resumed", run_id=str(run_id), decision=payload.decision)
    return {"status": "resuming", "run_id": str(run_id), "decision": payload.decision}
