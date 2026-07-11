"""SQLAlchemy ORM model — Organization."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="organization")  # type: ignore[name-defined]
    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="organization")  # type: ignore[name-defined]
    workflows: Mapped[list["Workflow"]] = relationship("Workflow", back_populates="organization")  # type: ignore[name-defined]
    api_keys: Mapped[list["ApiKey"]] = relationship("ApiKey", back_populates="organization")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        slug = self.__dict__.get("slug", "unknown")
        return f"<Organization {slug}>"
