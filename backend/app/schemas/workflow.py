"""Pydantic schemas — Workflow (nodes, edges, full graph)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ─── Node Schemas ──────────────────────────────────────────────────────────────

class WorkflowNodeBase(BaseModel):
    node_key: str = Field(..., max_length=255)
    node_type: str = Field(..., max_length=50)
    label: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    position_x: float = 0.0
    position_y: float = 0.0
    width: float | None = None
    height: float | None = None


class WorkflowNodeCreate(WorkflowNodeBase):
    pass


class WorkflowNodeResponse(WorkflowNodeBase):
    id: uuid.UUID
    workflow_id: uuid.UUID

    model_config = {"from_attributes": True}


# ─── Edge Schemas ──────────────────────────────────────────────────────────────

class WorkflowEdgeBase(BaseModel):
    edge_type: str = "default"
    condition: dict[str, Any] | None = None
    label: str | None = None
    priority: int = 0
    style: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdgeCreate(WorkflowEdgeBase):
    source_node_id: str
    target_node_id: str


class WorkflowEdgeResponse(WorkflowEdgeBase):
    id: uuid.UUID
    workflow_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID

    model_config = {"from_attributes": True}


# ─── Workflow Schemas ──────────────────────────────────────────────────────────

class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    is_cyclic: bool = False
    trigger_type: str = "manual"
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    viewport: dict[str, Any] = Field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})


class WorkflowCreate(WorkflowBase):
    nodes: list[WorkflowNodeCreate] = Field(default_factory=list)
    edges: list[WorkflowEdgeCreate] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_cyclic: bool | None = None
    trigger_type: str | None = None
    trigger_config: dict[str, Any] | None = None
    viewport: dict[str, Any] | None = None
    status: str | None = None
    # Replacing the full graph
    nodes: list[WorkflowNodeCreate] | None = None
    edges: list[WorkflowEdgeCreate] | None = None


class WorkflowResponse(WorkflowBase):
    id: uuid.UUID
    org_id: uuid.UUID
    created_by: uuid.UUID | None
    status: str
    version: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    nodes: list[WorkflowNodeResponse] = Field(default_factory=list)
    edges: list[WorkflowEdgeResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WorkflowListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_cyclic: bool
    trigger_type: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    items: list[WorkflowListItem]
    total: int
    page: int
    page_size: int


class WorkflowValidateResponse(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
    has_start: bool
    has_end: bool
    cycles_detected: list[list[str]]  # List of cycle node_key sequences
