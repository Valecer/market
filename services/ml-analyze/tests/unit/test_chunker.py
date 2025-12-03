"""
Unit Tests for Chunker
=======================

Tests for the Chunker class that converts NormalizedRow to ChunkData.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.ingest.chunker import Chunker, create_chunk
from src.schemas.domain import ChunkData, NormalizedRow


@pytest.fixture
def chunker() -> Chunker:
    """Create default Chunker instance."""
    return Chunker()


@pytest.fixture
def sample_row() -> NormalizedRow:
    """Create a sample normalized row."""
    return NormalizedRow(
        name="Батарейка AA Alkaline 1.5V",
        description="Щелочная батарейка типа АА",
        price=Decimal("25.50"),
        sku="BAT-AA-001",
        category="Батарейки",
        unit="шт",
        brand="Duracell",
        characteristics={"voltage": "1.5V", "type": "alkaline"},
    )


@pytest.fixture
def minimal_row() -> NormalizedRow:
    """Create a minimal row with only required fields."""
    return NormalizedRow(name="Simple Product")


class TestChunkerChunk:
    """Tests for Chunker.chunk() method."""

    def test_chunk_creates_chunk_data(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunking should create ChunkData with text."""
        chunk = chunker.chunk(sample_row)

        assert isinstance(chunk, ChunkData)
        assert chunk.text
        assert len(chunk.text) > 0

    def test_chunk_includes_name(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk text should include product name."""
        chunk = chunker.chunk(sample_row)

        assert sample_row.name in chunk.text

    def test_chunk_includes_description(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk text should include description when present."""
        chunk = chunker.chunk(sample_row)

        assert sample_row.description in chunk.text

    def test_chunk_includes_brand(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk text should include brand when present."""
        chunk = chunker.chunk(sample_row)

        assert sample_row.brand in chunk.text

    def test_chunk_includes_category(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk text should include category when present."""
        chunk = chunker.chunk(sample_row)

        assert sample_row.category in chunk.text

    def test_chunk_includes_sku(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk text should include SKU when present."""
        chunk = chunker.chunk(sample_row)

        assert sample_row.sku in chunk.text

    def test_chunk_includes_characteristics(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk text should include characteristics when enabled."""
        chunk = chunker.chunk(sample_row)

        assert "voltage" in chunk.text.lower() or "1.5V" in chunk.text

    def test_chunk_excludes_characteristics_when_disabled(
        self,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk text should exclude characteristics when disabled."""
        chunker = Chunker(include_characteristics=False)
        chunk = chunker.chunk(sample_row)

        # Characteristics keys should not appear
        assert "voltage:" not in chunk.text.lower()

    def test_chunk_minimal_row(
        self,
        chunker: Chunker,
        minimal_row: NormalizedRow,
    ) -> None:
        """Chunking minimal row should work with just name."""
        chunk = chunker.chunk(minimal_row)

        assert chunk.text == minimal_row.name

    def test_chunk_with_supplier_item_id(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk should preserve supplier_item_id."""
        item_id = uuid4()
        chunk = chunker.chunk(sample_row, item_id)

        assert chunk.supplier_item_id == item_id

    def test_chunk_metadata_includes_category(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk metadata should include category."""
        chunk = chunker.chunk(sample_row)

        assert chunk.metadata.get("category") == sample_row.category

    def test_chunk_metadata_includes_brand(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk metadata should include brand."""
        chunk = chunker.chunk(sample_row)

        assert chunk.metadata.get("brand") == sample_row.brand

    def test_chunk_metadata_includes_price(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Chunk metadata should include price as float."""
        chunk = chunker.chunk(sample_row)

        assert chunk.metadata.get("price") == float(sample_row.price)


class TestChunkerBatch:
    """Tests for Chunker.chunk_batch() method."""

    def test_chunk_batch_empty_list(self, chunker: Chunker) -> None:
        """Batch chunking empty list returns empty list."""
        chunks = chunker.chunk_batch([])

        assert chunks == []

    def test_chunk_batch_multiple_rows(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Batch chunking multiple rows returns multiple chunks."""
        rows = [sample_row, sample_row, sample_row]
        chunks = chunker.chunk_batch(rows)

        assert len(chunks) == 3

    def test_chunk_batch_with_ids(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Batch chunking with IDs preserves correspondence."""
        rows = [sample_row, sample_row]
        ids = [uuid4(), uuid4()]
        chunks = chunker.chunk_batch(rows, ids)

        assert len(chunks) == 2
        assert chunks[0].supplier_item_id == ids[0]
        assert chunks[1].supplier_item_id == ids[1]

    def test_chunk_batch_mismatched_ids_raises(
        self,
        chunker: Chunker,
        sample_row: NormalizedRow,
    ) -> None:
        """Batch chunking with mismatched ID count raises ValueError."""
        rows = [sample_row, sample_row]
        ids = [uuid4()]  # Only 1 ID for 2 rows

        with pytest.raises(ValueError, match="Length mismatch"):
            chunker.chunk_batch(rows, ids)


class TestChunkerTruncation:
    """Tests for text truncation behavior."""

    def test_truncate_long_text(self) -> None:
        """Long text should be truncated to max_length."""
        chunker = Chunker(max_length=50)
        row = NormalizedRow(name="A" * 100)

        chunk = chunker.chunk(row)

        assert len(chunk.text) <= 50
        assert chunk.text.endswith("...")

    def test_truncate_preserves_word_boundary(self) -> None:
        """Truncation should try to preserve word boundaries."""
        chunker = Chunker(max_length=30)
        row = NormalizedRow(name="Hello World This Is A Long Name")

        chunk = chunker.chunk(row)

        # Should not cut mid-word
        assert len(chunk.text) <= 30
        assert not chunk.text.endswith("Th...")  # Should cut at word boundary


class TestChunkerCharacteristics:
    """Tests for characteristics formatting."""

    def test_filter_internal_keys(
        self,
        chunker: Chunker,
    ) -> None:
        """Internal keys (starting with _) should be filtered."""
        row = NormalizedRow(
            name="Product",
            characteristics={
                "_source_row": 1,
                "_internal": "hidden",
                "visible": "shown",
            },
        )

        chunk = chunker.chunk(row)

        assert "_source_row" not in chunk.text
        assert "_internal" not in chunk.text
        assert "visible" in chunk.text.lower()

    def test_filter_none_values(
        self,
        chunker: Chunker,
    ) -> None:
        """None values in characteristics should be filtered."""
        row = NormalizedRow(
            name="Product",
            characteristics={
                "null_key": None,
                "empty_key": "",
                "valid_key": "valid",
            },
        )

        chunk = chunker.chunk(row)

        assert "null_key" not in chunk.text.lower()
        assert "valid_key" in chunk.text.lower()


class TestCreateChunkConvenience:
    """Tests for create_chunk convenience function."""

    def test_create_chunk_works(self, sample_row: NormalizedRow) -> None:
        """Convenience function should create chunk."""
        chunk = create_chunk(sample_row)

        assert isinstance(chunk, ChunkData)
        assert sample_row.name in chunk.text

    def test_create_chunk_with_id(self, sample_row: NormalizedRow) -> None:
        """Convenience function should accept item_id."""
        item_id = uuid4()
        chunk = create_chunk(sample_row, item_id)

        assert chunk.supplier_item_id == item_id

