"""ParsingLog ORM model for error tracking with semantic ETL phase support."""
from sqlalchemy import String, ForeignKey, Text, Integer, func, DateTime
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from src.db.models.supplier import Supplier


class ParsingLog(Base, UUIDMixin):
    """ParsingLog model for structured error logging.
    
    Phase 9 additions:
        - chunk_id: Chunk identifier for sliding window extraction
        - extraction_phase: Phase where error occurred (semantic ETL)
    """
    
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
    
    # Phase 9: Semantic ETL tracking fields
    chunk_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Chunk identifier for sliding window extraction"
    )
    extraction_phase: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc="Phase: sheet_selection, markdown_conversion, llm_extraction, category_matching"
    )
    
    # Relationships
    supplier: Mapped[Optional["Supplier"]] = relationship(back_populates="parsing_logs")
    
    def __repr__(self) -> str:
        return f"<ParsingLog(id={self.id}, type='{self.error_type}', phase='{self.extraction_phase}')>"

