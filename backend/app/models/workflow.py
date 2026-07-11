"""SQLAlchemy ORM models — Workflow, WorkflowNode, WorkflowEdge."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Graph metadata
    is_cyclic: Mapped[bool] = mapped_column(Boolean, default=False)
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual")
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Canvas viewport (React Flow serialization)
    viewport: Mapped[dict] = mapped_column(
        JSONB, default=lambda: {"x": 0, "y": 0, "zoom": 1}
    )

    # Status
    status: Mapped[str] = mapped_column(String(50), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="workflows")  # type: ignore[name-defined]
    creator: Mapped["User"] = relationship("User", back_populates="workflows")  # type: ignore[name-defined]
    nodes: Mapped[list["WorkflowNode"]] = relationship(
        "WorkflowNode", back_populates="workflow", cascade="all, delete-orphan"
    )
    edges: Mapped[list["WorkflowEdge"]] = relationship(
        "WorkflowEdge", back_populates="workflow", cascade="all, delete-orphan"
    )
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="workflow")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        name = self.__dict__.get("name", "unknown")
        status = self.__dict__.get("status", "unknown")
        return f"<Workflow {name} [{status}]>"


class WorkflowNode(Base):
    """
    A single node in the workflow graph.

    Node types map to execution behaviors in the engine:
    - 'start' / 'end'    → entry/exit points
    - 'agent'            → LLM agent invocation
    - 'tool'             → Tool dispatcher call
    - 'condition'        → Conditional branching (evaluates expression)
    - 'hitl_gate'        → Pause for human approval
    - 'memory_read/write'→ Memory operations
    - 'code'             → Docker sandbox code execution
    - 'subworkflow'      → Nested workflow invocation
    - 'parallel_fork'    → Spawn parallel branches
    - 'merge'            → Wait for parallel branches to rejoin
    """

    __tablename__ = "workflow_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_key: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)

    # React Flow canvas position
    position_x: Mapped[float] = mapped_column(Float, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)

    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    workflow: Mapped[Workflow] = relationship("Workflow", back_populates="nodes")
    outgoing_edges: Mapped[list["WorkflowEdge"]] = relationship(
        "WorkflowEdge", foreign_keys="WorkflowEdge.source_node_id", back_populates="source_node",
        cascade="all, delete-orphan"
    )
    incoming_edges: Mapped[list["WorkflowEdge"]] = relationship(
        "WorkflowEdge", foreign_keys="WorkflowEdge.target_node_id", back_populates="target_node",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        key = self.__dict__.get("node_key", "unknown")
        node_type = self.__dict__.get("node_type", "unknown")
        return f"<WorkflowNode {key} [{node_type}]>"


class WorkflowEdge(Base):
    """
    A directed edge between two nodes in the workflow graph.

    Edge types:
    - 'default'     → Always traverse
    - 'conditional' → Traverse if `condition` evaluates to True
    - 'error'       → Traverse on node error/exception
    - 'loop_back'   → Return edge that creates a cycle
    - 'parallel'    → Part of a parallel fork
    """

    __tablename__ = "workflow_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edge_type: Mapped[str] = mapped_column(String(50), default="default")
    condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    style: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    workflow: Mapped[Workflow] = relationship("Workflow", back_populates="edges")
    source_node: Mapped[WorkflowNode] = relationship(
        "WorkflowNode", foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target_node: Mapped[WorkflowNode] = relationship(
        "WorkflowNode", foreign_keys=[target_node_id], back_populates="incoming_edges"
    )

    def __repr__(self) -> str:
        source = self.__dict__.get("source_node_id", "unknown")
        target = self.__dict__.get("target_node_id", "unknown")
        edge_type = self.__dict__.get("edge_type", "unknown")
        return f"<WorkflowEdge {source} → {target} [{edge_type}]>"
