"""
SQLAlchemy ORM models — Run, RunStep, RunCheckpoint, Secret, AuditLog

Execution tracing models that capture the full state history of an agent run
for debugging, educational tracing, and HITL pause/resume.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DECIMAL, Boolean, DateTime, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Run(Base):
    """
    Represents a single execution of a workflow.

    A Run transitions through statuses:
      pending → running → (paused_hitl ↔ running) → completed | failed | cancelled | timeout
    """

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)

    # Execution data
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Metrics
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[Decimal] = mapped_column(DECIMAL(10, 6), default=Decimal("0"))

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # HITL pause/resume state
    current_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_nodes.id", ondelete="SET NULL"), nullable=True
    )
    checkpoint_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="runs")  # type: ignore[name-defined]
    triggered_by_user: Mapped["User | None"] = relationship("User", back_populates="runs")  # type: ignore[name-defined]
    steps: Mapped[list["RunStep"]] = relationship(
        "RunStep", back_populates="run", cascade="all, delete-orphan",
        order_by="RunStep.step_index"
    )
    checkpoints: Mapped[list["RunCheckpoint"]] = relationship(
        "RunCheckpoint", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        run_id = self.__dict__.get("id", "unknown")
        status = self.__dict__.get("status", "unknown")
        return f"<Run {run_id} [{status}]>"


class RunStep(Base):
    """
    Records every discrete action taken during a Run.

    Each step captures the full before/after state for educational debugging:
      - llm_call:       LLM prompt + response + token counts
      - tool_call:      Tool name, input, output
      - condition_eval: Expression and result
      - hitl_pause:     What was requested and who approved
      - memory_read:    Which memories were retrieved + similarity scores
      - memory_write:   What was stored
    """

    __tablename__ = "run_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Step identification
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_nodes.id", ondelete="SET NULL"), nullable=True
    )
    node_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # LLM interaction
    llm_request: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(DECIMAL(10, 6), default=Decimal("0"))

    # Tool interaction
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # State snapshots for trace debugger
    state_before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    state_after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    state_delta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Memory operations
    memories_retrieved: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    memories_stored: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error tracking
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    run: Mapped[Run] = relationship("Run", back_populates="steps")

    def __repr__(self) -> str:
        step_index = self.__dict__.get("step_index", "unknown")
        step_type = self.__dict__.get("step_type", "unknown")
        run_id = self.__dict__.get("run_id", "unknown")
        return f"<RunStep #{step_index} [{step_type}] run={run_id}>"


class RunCheckpoint(Base):
    """
    Serialized state snapshot at a specific point in execution.

    Used for:
      - HITL pause/resume — save full state, resume later
      - Time-travel debugging — replay from any checkpoint
      - Crash recovery — restart from last known good state
    """

    __tablename__ = "run_checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    run: Mapped[Run] = relationship("Run", back_populates="checkpoints")

    def __repr__(self) -> str:
        step_index = self.__dict__.get("step_index", "unknown")
        reason = self.__dict__.get("reason", "unknown")
        return f"<RunCheckpoint step={step_index} reason={reason}>"


class Secret(Base):
    """
    Encrypted secrets manager entry.

    Values are encrypted with AES-256-GCM before storage.
    The encryption key comes from settings.encryption_key.
    """

    __tablename__ = "secrets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(Text, nullable=False)  # base64-encoded
    encryption_iv: Mapped[bytes] = mapped_column(Text, nullable=False)   # base64-encoded IV
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        name = self.__dict__.get("name", "unknown")
        category = self.__dict__.get("category", "unknown")
        return f"<Secret {name} [{category}]>"


class AuditLog(Base):
    """
    Immutable audit trail for all significant platform actions.

    Every create/update/delete on sensitive resources is logged here
    for compliance and security auditing.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        action = self.__dict__.get("action", "unknown")
        user_id = self.__dict__.get("user_id", "unknown")
        return f"<AuditLog {action} by user={user_id}>"
