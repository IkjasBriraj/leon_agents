"""SQLAlchemy ORM models — Tool and AgentTool (junction)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification: 'builtin' | 'custom' | 'mcp'
    category: Mapped[str] = mapped_column(String(50), default="custom")

    # Tool definition — one of these is populated
    openapi_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    function_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    mcp_server_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON Schema for function calling parameters
    parameters_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Security & execution
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    sandbox_required: Mapped[bool] = mapped_column(Boolean, default=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    agent_tools: Mapped[list["AgentTool"]] = relationship("AgentTool", back_populates="tool")

    def __repr__(self) -> str:
        return f"<Tool {self.name} [{self.category}]>"


class AgentTool(Base):
    """Many-to-many junction: Agent ↔ Tool with per-agent config overrides."""

    __tablename__ = "agent_tools"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True
    )
    config_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="agent_tools")  # type: ignore[name-defined]
    tool: Mapped[Tool] = relationship("Tool", back_populates="agent_tools")
