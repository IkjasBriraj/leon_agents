"""
Pydantic schemas — Agent

Defines request/response models for the Agents API.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    model_provider: str = Field(default="ollama", max_length=50)
    model_name: str = Field(default="llama3.2", max_length=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    system_prompt: str = Field(..., min_length=1)
    persona: str | None = None
    instructions: list[Any] = Field(default_factory=list)
    max_iterations: int = Field(default=25, ge=1, le=200)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    tags: list[str] = Field(default_factory=list)


class AgentCreate(AgentBase):
    """Schema for creating a new agent."""
    pass


class AgentUpdate(BaseModel):
    """Schema for partial agent updates (all fields optional)."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=128000)
    top_p: float | None = Field(None, ge=0.0, le=1.0)
    system_prompt: str | None = None
    persona: str | None = None
    instructions: list[Any] | None = None
    max_iterations: int | None = Field(None, ge=1, le=200)
    timeout_seconds: int | None = Field(None, ge=10, le=3600)
    status: str | None = None
    tags: list[str] | None = None


class AgentResponse(AgentBase):
    """Schema for agent detail responses."""
    id: uuid.UUID
    org_id: uuid.UUID
    created_by: uuid.UUID | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListItem(BaseModel):
    """Lightweight agent listing item."""
    id: uuid.UUID
    name: str
    description: str | None
    model_provider: str
    model_name: str
    status: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    items: list[AgentListItem]
    total: int
    page: int
    page_size: int
