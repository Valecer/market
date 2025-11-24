"""ParsingLog ORM model for error tracking."""
from sqlalchemy import String, ForeignKey, Text, Integer, func, DateTime
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin
from datetime import datetime
from typing import Optional, Dict, Any
import uuid


class ParsingLog(Base, UUIDMixin):
    """ParsingLog model for structured error logging."""
    
    __tablename__ = "parsing_logs"
    
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    error_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_data: Mapped[Dict[str, Any] | None] = mapped_column(
        postgresql.JSONB(astext_type=Text),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    supplier: Mapped[Optional["Supplier"]] = relationship(back_populates="parsing_logs")
    
    def __repr__(self) -> str:
        return f"<ParsingLog(id={self.id}, type='{self.error_type}', task='{self.task_id}')>"

