"""SQLAlchemy ORM model — Agent."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Model Configuration ────────────────────────────────────────────────
    # Default to Ollama provider
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="ollama")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="llama3.2")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    top_p: Mapped[float] = mapped_column(Float, default=1.0)

    # ─── Behavioral Configuration ───────────────────────────────────────────
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    persona: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[list] = mapped_column(JSONB, default=list)

    # ─── Execution Limits ───────────────────────────────────────────────────
    max_iterations: Mapped[int] = mapped_column(Integer, default=25)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)

    # ─── Status ─────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="agents")  # type: ignore[name-defined]
    creator: Mapped["User"] = relationship("User", back_populates="agents")  # type: ignore[name-defined]
    agent_tools: Mapped[list["AgentTool"]] = relationship("AgentTool", back_populates="agent", cascade="all, delete-orphan")
    memories: Mapped[list["Memory"]] = relationship("Memory", back_populates="agent")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Agent {self.name} ({self.model_provider}/{self.model_name})>"
