"""Database base class for all SQLAlchemy ORM models."""

import re
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase class name to snake_case table name."""
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


class Base(DeclarativeBase):
    """
    Shared base for all ORM models.

    Auto-generates table names from class name (CamelCase → snake_case).
    All models inherit `created_at` and `updated_at` timestamps.
    """

    @classmethod
    def __tablename__(cls) -> str:  # type: ignore[override]
        return _camel_to_snake(cls.__name__)
