"""
Chunker - Row-to-Chunk Converter
================================

Converts normalized rows into semantic chunks for embedding generation.
Each chunk contains concatenated text optimized for the embedding model.

Follows Single Responsibility Principle: Only handles chunking logic.
"""

from typing import Any
from uuid import UUID

from src.schemas.domain import ChunkData, NormalizedRow
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Chunker:
    """
    Converts normalized product rows into semantic chunks for embeddings.

    Design Philosophy (KISS):
        - Simple 1:1 mapping: 1 product row = 1 chunk
        - Text is concatenated in semantic order: name → description → characteristics
        - Metadata preserved for traceability

    Future Evolution:
        - Multi-row descriptions can be grouped
        - Hierarchical chunking for large documents
        - Overlap-based chunking if needed for RAG recall
    """

    # Default separator for joining text fields
    DEFAULT_SEPARATOR = " | "
    # Maximum chunk text length (for embedding model limits)
    MAX_CHUNK_LENGTH = 8192  # nomic-embed-text supports up to 8192 tokens

    def __init__(
        self,
        separator: str = DEFAULT_SEPARATOR,
        max_length: int = MAX_CHUNK_LENGTH,
        include_characteristics: bool = True,
    ) -> None:
        """
        Initialize Chunker.

        Args:
            separator: Text separator between fields
            max_length: Maximum chunk text length
            include_characteristics: Whether to include characteristics in chunk text
        """
        self.separator = separator
        self.max_length = max_length
        self.include_characteristics = include_characteristics
        logger.debug(
            "Chunker initialized",
            separator=separator,
            max_length=max_length,
            include_characteristics=include_characteristics,
        )

    def chunk(
        self,
        row: NormalizedRow,
        supplier_item_id: UUID | None = None,
    ) -> ChunkData:
        """
        Convert a normalized row into a semantic chunk.

        The text is constructed by concatenating:
        1. Product name (required)
        2. Description (if present)
        3. Brand (if present)
        4. Category (if present)
        5. Key characteristics (if enabled and present)

        Args:
            row: Normalized product row from parser
            supplier_item_id: Optional reference to supplier_items table

        Returns:
            ChunkData containing semantic text and metadata

        Example:
            Input: NormalizedRow(name="AA Battery", brand="Duracell", category="Batteries")
            Output: ChunkData(text="AA Battery | Duracell | Batteries", metadata=...)
        """
        parts: list[str] = []

        # 1. Name is always included (required field)
        parts.append(row.name.strip())

        # 2. Description provides additional context
        if row.description:
            desc = row.description.strip()
            if desc:
                parts.append(desc)

        # 3. Brand is valuable for matching
        if row.brand:
            brand = row.brand.strip()
            if brand:
                parts.append(brand)

        # 4. Category helps with semantic context
        if row.category:
            cat = row.category.strip()
            if cat:
                parts.append(cat)

        # 5. SKU can help with exact matches
        if row.sku:
            sku = row.sku.strip()
            if sku:
                parts.append(f"SKU: {sku}")

        # 6. Key characteristics (if enabled)
        if self.include_characteristics and row.characteristics:
            char_text = self._format_characteristics(row.characteristics)
            if char_text:
                parts.append(char_text)

        # Join and truncate
        text = self.separator.join(parts)
        text = self._truncate_text(text)

        # Build metadata
        metadata = self._build_metadata(row)

        return ChunkData(
            text=text,
            supplier_item_id=supplier_item_id,
            metadata=metadata,
        )

    def chunk_batch(
        self,
        rows: list[NormalizedRow],
        supplier_item_ids: list[UUID] | None = None,
    ) -> list[ChunkData]:
        """
        Convert multiple normalized rows into chunks.

        Args:
            rows: List of normalized rows
            supplier_item_ids: Optional list of supplier_item_ids (parallel with rows)

        Returns:
            List of ChunkData objects

        Raises:
            ValueError: If supplier_item_ids provided but length doesn't match rows
        """
        if supplier_item_ids and len(supplier_item_ids) != len(rows):
            raise ValueError(
                f"Length mismatch: {len(rows)} rows vs {len(supplier_item_ids)} IDs"
            )

        chunks: list[ChunkData] = []
        for i, row in enumerate(rows):
            item_id = supplier_item_ids[i] if supplier_item_ids else None
            try:
                chunk = self.chunk(row, item_id)
                chunks.append(chunk)
            except Exception as e:
                logger.warning(
                    "Failed to chunk row, skipping",
                    row_index=i,
                    name=row.name[:50] if row.name else None,
                    error=str(e),
                )
                continue

        logger.debug(
            "Batch chunking complete",
            input_rows=len(rows),
            output_chunks=len(chunks),
        )
        return chunks

    def _format_characteristics(self, characteristics: dict[str, Any]) -> str:
        """
        Format characteristics dictionary as readable text.

        Args:
            characteristics: Key-value dictionary of product attributes

        Returns:
            Formatted string like "color: red, size: large"
        """
        if not characteristics:
            return ""

        # Filter out internal keys (starting with _) and None values
        filtered = {
            k: v
            for k, v in characteristics.items()
            if not k.startswith("_") and v is not None and str(v).strip()
        }

        if not filtered:
            return ""

        # Format as "key: value" pairs
        pairs = [f"{k}: {v}" for k, v in filtered.items()]
        return ", ".join(pairs)

    def _truncate_text(self, text: str) -> str:
        """
        Truncate text to maximum length.

        Truncates at word boundary when possible to avoid cutting mid-word.

        Args:
            text: Input text

        Returns:
            Truncated text (with "..." suffix if truncated)
        """
        if len(text) <= self.max_length:
            return text

        # Find last space before limit
        truncate_at = text.rfind(" ", 0, self.max_length - 3)
        if truncate_at == -1:
            truncate_at = self.max_length - 3

        truncated = text[:truncate_at].rstrip() + "..."

        logger.debug(
            "Text truncated",
            original_length=len(text),
            truncated_length=len(truncated),
        )
        return truncated

    def _build_metadata(self, row: NormalizedRow) -> dict[str, Any]:
        """
        Build metadata dictionary from normalized row.

        Args:
            row: Source normalized row

        Returns:
            Metadata dict for chunk
        """
        metadata: dict[str, Any] = {}

        if row.category:
            metadata["category"] = row.category
        if row.brand:
            metadata["brand"] = row.brand
        if row.sku:
            metadata["sku"] = row.sku
        if row.price is not None:
            metadata["price"] = float(row.price)
        if row.unit:
            metadata["unit"] = row.unit

        return metadata


# Convenience function for simple chunking
def create_chunk(row: NormalizedRow, item_id: UUID | None = None) -> ChunkData:
    """
    Create a chunk from a normalized row using default settings.

    Args:
        row: Normalized product row
        item_id: Optional supplier_item_id reference

    Returns:
        ChunkData with semantic text
    """
    chunker = Chunker()
    return chunker.chunk(row, item_id)

