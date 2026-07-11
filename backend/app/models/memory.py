"""
SQLAlchemy ORM model — Memory

The dual-memory layer stores three types of memories:
  - episodic:  Past run interactions, successes, and failures
  - semantic:  Knowledge base facts, documents, company data
  - profile:   Agent preferences, rules, behavioral constraints

Vector embeddings are stored using pgvector for semantic retrieval.
NOTE: We use 768 dimensions to match nomic-embed-text (Ollama).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# pgvector import — graceful fallback if extension not installed
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_TYPE = Vector(768)  # nomic-embed-text dimensions
except ImportError:
    from sqlalchemy import LargeBinary
    VECTOR_TYPE = LargeBinary()  # Fallback — won't support similarity search


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # ─── Memory classification ────────────────────────────────────────────────
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # 'episodic' | 'semantic' | 'profile'

    # ─── Content ─────────────────────────────────────────────────────────────
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vector embedding (pgvector) — 768 dimensions for nomic-embed-text
    # Stored as a column using SQLAlchemy mapped_column with VECTOR type
    embedding: Mapped[list | None] = mapped_column(VECTOR_TYPE, nullable=True)  # type: ignore[assignment]

    # ─── Metadata ─────────────────────────────────────────────────────────────
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    # For episodic: {run_id, step_index, outcome}
    # For semantic: {source, doc_id, chunk_index}
    # For profile:  {category: preference|rule|constraint}
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # ─── Relevance scoring ────────────────────────────────────────────────────
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ─── Lifecycle ─────────────────────────────────────────────────────────────
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="memories")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        content = self.__dict__.get("content", "")
        memory_type = self.__dict__.get("memory_type", "unknown")
        preview = content[:40] + "..." if len(content) > 40 else content
        return f"<Memory [{memory_type}] {preview!r}>"
