"""Workflows API router — /api/v1/workflows"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowListItem,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
    WorkflowValidateResponse,
)
from app.core.graph import WorkflowGraph

log = structlog.get_logger()
router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowListResponse:
    """List workflows for the current organization (paginated)."""
    query = select(Workflow).where(Workflow.org_id == current_user.org_id)
    if status_filter:
        query = query.where(Workflow.status == status_filter)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Workflow.created_at.desc())
    result = await db.execute(query)
    workflows = result.scalars().all()

    return WorkflowListResponse(items=list(workflows), total=total, page=page, page_size=page_size)


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Workflow:
    """Create a new workflow with initial nodes and edges."""
    workflow = Workflow(
        org_id=current_user.org_id,
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
        is_cyclic=payload.is_cyclic,
        trigger_type=payload.trigger_type,
        trigger_config=payload.trigger_config,
        viewport=payload.viewport,
        status="draft",
        version=1,
    )
    db.add(workflow)
    await db.flush()

    # Create associated nodes
    for node in payload.nodes:
        db_node = WorkflowNode(
            workflow_id=workflow.id,
            node_key=node.node_key,
            node_type=node.node_type,
            label=node.label,
            config=node.config,
            position_x=node.position_x,
            position_y=node.position_y,
        )
        db.add(db_node)

    await db.commit()
    await db.refresh(workflow)

    # Reload with relationships loaded
    result = await db.execute(
        select(Workflow)
        .where(Workflow.id == workflow.id)
        .options(selectinload(Workflow.nodes), selectinload(Workflow.edges))
    )
    log.info("workflow.created", workflow_id=str(workflow.id), name=workflow.name)
    return result.scalar_one()


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Workflow:
    """Get workflow details including all nodes and edges."""
    result = await db.execute(
        select(Workflow)
        .where(Workflow.id == workflow_id, Workflow.org_id == current_user.org_id)
        .options(selectinload(Workflow.nodes), selectinload(Workflow.edges))
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return workflow


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Workflow:
    """
    Update workflow configuration and replace the node/edge layout.

    For simplicity, when nodes or edges are updated, we wipe the existing
    nodes/edges and insert the new ones.
    """
    result = await db.execute(
        select(Workflow)
        .where(Workflow.id == workflow_id, Workflow.org_id == current_user.org_id)
        .options(selectinload(Workflow.nodes), selectinload(Workflow.edges))
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    # Update basic fields
    basic_fields = ["name", "description", "is_cyclic", "trigger_type", "trigger_config", "viewport", "status"]
    for field in basic_fields:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(workflow, field, val)

    # Handle nodes replacement if provided
    if payload.nodes is not None:
        # Delete old nodes
        for node in workflow.nodes:
            await db.delete(node)
        await db.flush()

        # Insert new nodes
        node_map = {}  # key -> db.id (to resolve edge source/targets)
        for node in payload.nodes:
            db_node = WorkflowNode(
                workflow_id=workflow.id,
                node_key=node.node_key,
                node_type=node.node_type,
                label=node.label,
                config=node.config,
                position_x=node.position_x,
                position_y=node.position_y,
            )
            db.add(db_node)
            await db.flush()
            node_map[node.node_key] = db_node.id

        # Handle edges replacement if provided
        if payload.edges is not None:
            # Delete old edges
            for edge in workflow.edges:
                await db.delete(edge)
            await db.flush()

            # Insert new edges (resolving source/target node keys to DB IDs)
            for edge in payload.edges:
                # We expect source_node_id and target_node_id to contain the string node_key
                # in the incoming payload from the React Flow UI.
                src_key = str(edge.source_node_id)
                tgt_key = str(edge.target_node_id)

                src_id = node_map.get(src_key)
                tgt_id = node_map.get(tgt_key)

                if src_id and tgt_id:
                    db_edge = WorkflowEdge(
                        workflow_id=workflow.id,
                        source_node_id=src_id,
                        target_node_id=tgt_id,
                        edge_type=edge.edge_type,
                        condition=edge.condition,
                        label=edge.label,
                        priority=edge.priority,
                        style=edge.style,
                    )
                    db.add(db_edge)

    workflow.version += 1
    await db.commit()
    await db.refresh(workflow)

    # Re-fetch fully loaded
    final_result = await db.execute(
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.nodes), selectinload(Workflow.edges))
    )
    log.info("workflow.updated", workflow_id=str(workflow_id), version=workflow.version)
    return final_result.scalar_one()


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a workflow."""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.org_id == current_user.org_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    await db.delete(workflow)
    await db.commit()
    log.info("workflow.deleted", workflow_id=str(workflow_id))


@router.get("/{workflow_id}/validate", response_model=WorkflowValidateResponse)
async def validate_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Run graph validation and cycle checks."""
    result = await db.execute(
        select(Workflow)
        .where(Workflow.id == workflow_id, Workflow.org_id == current_user.org_id)
        .options(selectinload(Workflow.nodes), selectinload(Workflow.edges))
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    graph = WorkflowGraph.from_orm(workflow)
    valid, errors, warnings = graph.validate()
    cycles = graph.detect_cycles()

    # If status changes, update model in db
    is_cyclic = len(cycles) > 0
    if workflow.is_cyclic != is_cyclic:
        workflow.is_cyclic = is_cyclic
        await db.commit()

    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "has_start": any(n.node_type == "start" for n in workflow.nodes),
        "has_end": any(n.node_type == "end" for n in workflow.nodes),
        "cycles_detected": cycles,
    }
