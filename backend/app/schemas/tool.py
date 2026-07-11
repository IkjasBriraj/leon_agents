"""Pydantic schemas — Tool (read, write, register)."""

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ToolCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Unique name of the tool for LLM function calling")
    description: str = Field(..., min_length=1, description="Description explaining when to invoke the tool")
    category: str = Field("custom", description="builtin, custom, or mcp")
    openapi_spec: dict[str, Any] | None = Field(None, description="OpenAPI specification for REST API tools")
    function_code: str | None = Field(None, description="Raw python code for custom tools")
    mcp_server_url: str | None = Field(None, description="MCP server SSE or transport connection string")
    parameters_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for function calling parameters")
    requires_approval: bool = Field(False, description="HITL human verification check prior to launch")
    sandbox_required: bool = Field(False, description="Run tool script inside secure Docker container")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Max execution time limit")


class ToolUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    openapi_spec: dict[str, Any] | None = None
    function_code: str | None = None
    mcp_server_url: str | None = None
    parameters_schema: dict[str, Any] | None = None
    requires_approval: bool | None = None
    sandbox_required: bool | None = None
    timeout_seconds: int | None = None
    is_active: bool | None = None


class ToolResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID | None = None
    name: str
    description: str
    category: str
    openapi_spec: dict[str, Any] | None = None
    function_code: str | None = None
    mcp_server_url: str | None = None
    parameters_schema: dict[str, Any]
    requires_approval: bool
    sandbox_required: bool
    timeout_seconds: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentToolConfig(BaseModel):
    tool_id: uuid.UUID
    config_overrides: dict[str, Any] = Field(default_factory=dict)
