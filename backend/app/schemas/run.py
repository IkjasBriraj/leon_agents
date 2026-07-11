"""Pydantic schemas — Run, RunStep, WebSocket trace events."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    workflow_id: uuid.UUID
    input_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunStepResponse(BaseModel):
    id: uuid.UUID
    step_index: int
    node_key: str | None
    step_type: str
    model_used: str | None
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    tool_name: str | None
    tool_input: dict | None
    tool_output: dict | None
    state_before: dict | None
    state_after: dict | None
    state_delta: dict | None
    memories_retrieved: dict | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    error: dict | None

    model_config = {"from_attributes": True}


class RunResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    workflow_id: uuid.UUID | None
    status: str
    input_data: dict
    output_data: dict | None
    error: dict | None
    total_steps: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: Decimal
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime
    steps: list[RunStepResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RunListItem(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID | None
    status: str
    total_steps: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: Decimal
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    items: list[RunListItem]
    total: int
    page: int
    page_size: int


class RunResumePayload(BaseModel):
    """Payload sent when a human resumes a HITL-paused run."""
    decision: Literal["approve", "reject"]
    edited_state: dict[str, Any] | None = None  # Human can edit intermediate state
    message: str | None = None  # Human's comment/instructions


# ─── WebSocket Trace Event Schemas ────────────────────────────────────────────

class WsEventStepStart(BaseModel):
    type: Literal["step_start"] = "step_start"
    run_id: str
    step_index: int
    node_key: str
    node_type: str
    timestamp: str


class WsEventStepEnd(BaseModel):
    type: Literal["step_end"] = "step_end"
    run_id: str
    step_index: int
    state_delta: dict
    tokens_in: int
    tokens_out: int
    duration_ms: int
    timestamp: str


class WsEventLlmStream(BaseModel):
    type: Literal["llm_stream"] = "llm_stream"
    run_id: str
    step_index: int
    chunk: str


class WsEventToolCalled(BaseModel):
    type: Literal["tool_called"] = "tool_called"
    run_id: str
    step_index: int
    tool_name: str
    tool_input: dict


class WsEventHitlRequired(BaseModel):
    type: Literal["hitl_required"] = "hitl_required"
    run_id: str
    step_index: int
    node_key: str
    message: str
    approval_roles: list[str]


class WsEventMemoryRetrieved(BaseModel):
    type: Literal["memory_retrieved"] = "memory_retrieved"
    run_id: str
    step_index: int
    memories: list[dict]
    scores: list[float]


class WsEventRunComplete(BaseModel):
    type: Literal["run_complete"] = "run_complete"
    run_id: str
    status: str
    output: dict | None
    total_cost_usd: float
    total_tokens: int
    duration_ms: int


class WsEventRunError(BaseModel):
    type: Literal["run_error"] = "run_error"
    run_id: str
    error: dict
    step_index: int | None
