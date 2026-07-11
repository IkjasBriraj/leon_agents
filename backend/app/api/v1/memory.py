"""Memory API router — /api/v1/memory"""

import structlog
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.memory import Memory
from app.schemas.memory import (
    MemoryCreateRequest,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
)
from app.core.memory_manager import MemoryManager

log = structlog.get_logger()
router = APIRouter(prefix="/memory", tags=["Memory Explorer"])


@router.post("/search", response_model=list[MemorySearchResponse])
async def search_memories(
    payload: MemorySearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MemorySearchResponse]:
    """Search organization's memories semantically using vector embeddings."""
    try:
        manager = MemoryManager(
            db=db,
            org_id=current_user.org_id,
            agent_id=payload.agent_id,
        )
        
        # Determine memory types to filter by
        memory_types = [payload.memory_type] if payload.memory_type else None
        
        results = await manager.retrieve_relevant(
            query=payload.query,
            k=payload.limit,
            memory_types=memory_types,
        )
        
        # Map to search response schema
        response_items = []
        for r in results:
            response_items.append(
                MemorySearchResponse(
                    memory=MemoryResponse.model_validate(r.memory),
                    score=r.score,
                )
            )
        return response_items
    except Exception as exc:
        log.error("api.memory.search_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic memory search failed: {str(exc)}"
        ) from exc


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryResponse:
    """Manually ingest and store a new memory (e.g. semantic document or profile rule)."""
    try:
        manager = MemoryManager(
            db=db,
            org_id=current_user.org_id,
            agent_id=payload.agent_id,
        )
        
        if payload.memory_type == "semantic":
            created_memories = await manager.store_semantic(
                content=payload.content,
                metadata=payload.metadata,
                tags=payload.tags,
                importance=payload.importance,
            )
            if not created_memories:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No memory chunks created"
                )
            # Commit the session changes
            await db.commit()
            return MemoryResponse.model_validate(created_memories[0])
            
        elif payload.memory_type == "profile":
            category = payload.metadata.get("category", "preference")
            memory = await manager.store_profile(
                content=payload.content,
                category=category,
                importance=payload.importance,
            )
            await db.commit()
            return MemoryResponse.model_validate(memory)
            
        else:
            # Fallback to episodic or simple custom storage
            memory = await manager.store_episodic(
                content=payload.content,
                metadata=payload.metadata,
                importance=payload.importance,
                tags=payload.tags,
            )
            await db.commit()
            return MemoryResponse.model_validate(memory)
            
    except Exception as exc:
        log.error("api.memory.create_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save memory: {str(exc)}"
        ) from exc


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    agent_id: uuid.UUID | None = None,
    memory_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MemoryResponse]:
    """Retrieve all memories in the current organization (paginated)."""
    query = select(Memory).where(Memory.org_id == current_user.org_id)
    
    if agent_id:
        query = query.where(Memory.agent_id == agent_id)
    if memory_type:
        query = query.where(Memory.memory_type == memory_type)
        
    query = query.order_by(Memory.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    memories = result.scalars().all()
    
    return [MemoryResponse.model_validate(m) for m in memories]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a memory permanently by ID."""
    query = delete(Memory).where(
        Memory.id == memory_id,
        Memory.org_id == current_user.org_id
    )
    result = await db.execute(query)
    await db.commit()
    
    if result.rowcount == 0:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND,
             detail="Memory not found or unauthorized"
         )
