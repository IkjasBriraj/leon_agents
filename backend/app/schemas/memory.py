"""Pydantic schemas — Memory (read, write, search)."""

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class MemorySearchRequest(BaseModel):
    query: str = Field(..., description="Query string to search in memories via embeddings")
    agent_id: uuid.UUID | None = Field(None, description="Filter memories by agent ID")
    memory_type: str | None = Field(None, description="Filter memories by memory type: episodic, semantic, profile")
    limit: int = Field(5, ge=1, le=50, description="Max number of results to return")


class MemoryCreateRequest(BaseModel):
    agent_id: uuid.UUID | None = Field(None, description="Optional agent ID this memory belongs to")
    memory_type: str = Field("semantic", description="episodic, semantic, or profile")
    content: str = Field(..., min_length=1, description="Raw content of the memory")
    tags: list[str] = Field(default_factory=list, description="Associated tags for filtering")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata dictionary")
    importance: float = Field(0.5, ge=0.0, le=1.0, description="Importance score of the memory")
    expires_at: datetime | None = Field(None, description="Optional TTL expiration timestamp")


class MemoryResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    memory_type: str
    content: str
    summary: str | None = None
    tags: list[str]
    metadata: dict[str, Any] = Field(..., alias="metadata_")
    importance: float
    access_count: int
    last_accessed: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


class MemorySearchResponse(BaseModel):
    memory: MemoryResponse
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
