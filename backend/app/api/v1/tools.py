"""Tools API router — /api/v1/tools"""

import structlog
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.tool import Tool
from app.schemas.tool import ToolCreateRequest, ToolResponse, ToolUpdateRequest

log = structlog.get_logger()
router = APIRouter(prefix="/tools", tags=["Tools Registry"])


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ToolResponse]:
    """List all registered tools in the organization, including builtin ones."""
    # List tools owned by org, OR system-wide builtin tools (where org_id is null)
    query = select(Tool).where(
        (Tool.org_id == current_user.org_id) | (Tool.org_id == None)
    ).order_by(Tool.created_at.desc())
    
    result = await db.execute(query)
    tools = result.scalars().all()
    
    return [ToolResponse.model_validate(t) for t in tools]


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def register_tool(
    payload: ToolCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ToolResponse:
    """Register a new custom code, API, or MCP tool."""
    # Check duplicate tool name within org
    result = await db.execute(
        select(Tool).where(
            Tool.name == payload.name,
            Tool.org_id == current_user.org_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool with name '{payload.name}' already registered in your organization"
        )
        
    tool = Tool(
        org_id=current_user.org_id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        openapi_spec=payload.openapi_spec,
        function_code=payload.function_code,
        mcp_server_url=payload.mcp_server_url,
        parameters_schema=payload.parameters_schema,
        requires_approval=payload.requires_approval,
        sandbox_required=payload.sandbox_required,
        timeout_seconds=payload.timeout_seconds,
        is_active=True,
    )
    
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    
    log.info("tool.registered", tool_id=str(tool.id), name=tool.name, org_id=str(current_user.org_id))
    return ToolResponse.model_validate(tool)


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: uuid.UUID,
    payload: ToolUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ToolResponse:
    """Update a custom tool's registration schema or settings."""
    # Fetch tool to verify ownership
    result = await db.execute(
        select(Tool).where(
            Tool.id == tool_id,
            Tool.org_id == current_user.org_id
        )
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found or access denied"
        )
        
    # Update fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tool, field, value)
        
    await db.commit()
    await db.refresh(tool)
    
    log.info("tool.updated", tool_id=str(tool.id), name=tool.name)
    return ToolResponse.model_validate(tool)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Deregister and delete a tool from the organization."""
    query = delete(Tool).where(
        Tool.id == tool_id,
        Tool.org_id == current_user.org_id
    )
    result = await db.execute(query)
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found or access denied"
        )
        
    log.info("tool.deleted", tool_id=str(tool_id))
