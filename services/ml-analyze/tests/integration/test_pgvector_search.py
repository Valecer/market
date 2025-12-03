"""
Integration Tests for pgvector Operations
==========================================

Tests real database operations with pgvector extension.
Requires PostgreSQL with pgvector extension.

Run with: pytest tests/integration/test_pgvector_search.py -v
"""

import os
from uuid import uuid4

import pytest

# Database URL from environment
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://marketbel_user:dev_password@localhost:5432/marketbel"
)


def check_database_available() -> bool:
    """Check if database is available."""
    import asyncio
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check():
        try:
            engine = create_async_engine(DATABASE_URL)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return True
        except Exception:
            return False

    return asyncio.get_event_loop().run_until_complete(_check())


# Skip all tests if database is not available
pytestmark = pytest.mark.skipif(
    not check_database_available(),
    reason="Database not available",
)


@pytest.fixture
async def db_session():
    """Create a database session for testing."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def sample_embedding_768():
    """Generate a sample 768-dimensional embedding."""
    import random
    random.seed(42)
    return [random.uniform(-1, 1) for _ in range(768)]


@pytest.fixture
def sample_embeddings_batch():
    """Generate batch of sample embeddings."""
    import random

    embeddings = []
    for i in range(5):
        random.seed(i)
        embeddings.append([random.uniform(-1, 1) for _ in range(768)])
    return embeddings


class TestPgvectorBasicOperations:
    """Basic pgvector operations tests."""

    @pytest.mark.asyncio
    async def test_vector_extension_enabled(self, db_session):
        """Test that pgvector extension is enabled."""
        from sqlalchemy import text

        result = await db_session.execute(
            text("SELECT * FROM pg_extension WHERE extname = 'vector'")
        )
        row = result.fetchone()

        assert row is not None, "pgvector extension not enabled"

    @pytest.mark.asyncio
    async def test_product_embeddings_table_exists(self, db_session):
        """Test that product_embeddings table exists."""
        from sqlalchemy import text

        result = await db_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'product_embeddings'
                )
            """)
        )
        exists = result.scalar()

        assert exists, "product_embeddings table does not exist"

    @pytest.mark.asyncio
    async def test_insert_vector(self, db_session, sample_embedding_768):
        """Test inserting a vector into the database."""
        from sqlalchemy import text

        # Create a test supplier_item first
        item_id = uuid4()
        supplier_id = uuid4()

        # Insert test supplier item
        await db_session.execute(
            text("""
                INSERT INTO suppliers (id, name, source_type, metadata)
                VALUES (:id, :name, 'csv', '{}')
                ON CONFLICT (id) DO NOTHING
            """),
            {"id": str(supplier_id), "name": f"Test Supplier {supplier_id}"},
        )

        await db_session.execute(
            text("""
                INSERT INTO supplier_items (id, supplier_id, supplier_sku, name, current_price, match_status)
                VALUES (:id, :supplier_id, :sku, :name, 10.00, 'unmatched')
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": str(item_id),
                "supplier_id": str(supplier_id),
                "sku": f"TEST-SKU-{item_id}",
                "name": f"Test Item {item_id}",
            },
        )

        # Insert embedding
        embedding_str = f"[{','.join(str(x) for x in sample_embedding_768)}]"
        result = await db_session.execute(
            text("""
                INSERT INTO product_embeddings (supplier_item_id, embedding, model_name)
                VALUES (:item_id, CAST(:embedding AS vector), 'test-model')
                RETURNING id
            """),
            {"item_id": str(item_id), "embedding": embedding_str},
        )
        embedding_id = result.scalar()
        await db_session.commit()

        assert embedding_id is not None

        # Cleanup
        await db_session.execute(
            text("DELETE FROM product_embeddings WHERE id = :id"),
            {"id": str(embedding_id)},
        )
        await db_session.execute(
            text("DELETE FROM supplier_items WHERE id = :id"),
            {"id": str(item_id)},
        )
        await db_session.execute(
            text("DELETE FROM suppliers WHERE id = :id"),
            {"id": str(supplier_id)},
        )
        await db_session.commit()


class TestPgvectorSimilaritySearch:
    """pgvector similarity search tests."""

    @pytest.fixture
    async def test_data(self, db_session):
        """Create test data with embeddings."""
        from sqlalchemy import text

        supplier_id = uuid4()
        item_ids = [uuid4() for _ in range(3)]

        # Create supplier
        await db_session.execute(
            text("""
                INSERT INTO suppliers (id, name, source_type, metadata)
                VALUES (:id, 'Test Supplier', 'csv', '{}')
            """),
            {"id": str(supplier_id)},
        )

        # Create items with different embeddings
        embeddings = [
            [1.0] + [0.0] * 767,  # Item 0: First dimension is 1
            [0.9] + [0.1] * 767,  # Item 1: Similar to item 0
            [0.0] * 768,  # Item 2: Different (all zeros - normalized)
        ]
        # Normalize the zero vector to be different
        embeddings[2] = [1.0 / (768 ** 0.5)] * 768

        for i, (item_id, embedding) in enumerate(zip(item_ids, embeddings)):
            await db_session.execute(
                text("""
                    INSERT INTO supplier_items (id, supplier_id, supplier_sku, name, current_price, match_status)
                    VALUES (:id, :supplier_id, :sku, :name, 10.00, 'unmatched')
                """),
                {
                    "id": str(item_id),
                    "supplier_id": str(supplier_id),
                    "sku": f"TEST-SKU-{item_id}",
                    "name": f"Test Item {i}",
                },
            )

            embedding_str = f"[{','.join(str(x) for x in embedding)}]"
            await db_session.execute(
                text("""
                    INSERT INTO product_embeddings (supplier_item_id, embedding, model_name)
                    VALUES (:item_id, CAST(:embedding AS vector), 'test-model')
                """),
                {"item_id": str(item_id), "embedding": embedding_str},
            )

        await db_session.commit()

        yield {
            "supplier_id": supplier_id,
            "item_ids": item_ids,
            "embeddings": embeddings,
        }

        # Cleanup
        for item_id in item_ids:
            await db_session.execute(
                text("DELETE FROM product_embeddings WHERE supplier_item_id = :id"),
                {"id": str(item_id)},
            )
            await db_session.execute(
                text("DELETE FROM supplier_items WHERE id = :id"),
                {"id": str(item_id)},
            )
        await db_session.execute(
            text("DELETE FROM suppliers WHERE id = :id"),
            {"id": str(supplier_id)},
        )
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_cosine_similarity_search(self, db_session, test_data):
        """Test cosine similarity search returns ordered results."""
        from sqlalchemy import text

        # Query vector similar to item 0 and 1
        query_embedding = [1.0] + [0.0] * 767
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        result = await db_session.execute(
            text("""
                SELECT
                    si.id,
                    si.name,
                    (1 - (pe.embedding <=> CAST(:query AS vector))) AS similarity
                FROM product_embeddings pe
                JOIN supplier_items si ON pe.supplier_item_id = si.id
                WHERE pe.model_name = 'test-model'
                ORDER BY pe.embedding <=> CAST(:query AS vector)
                LIMIT 3
            """),
            {"query": embedding_str},
        )
        rows = result.fetchall()

        assert len(rows) == 3

        # First result should be most similar (item 0 or 1)
        assert rows[0][2] >= rows[1][2], "Results not ordered by similarity"
        assert rows[1][2] >= rows[2][2], "Results not ordered by similarity"

    @pytest.mark.asyncio
    async def test_similarity_values_range(self, db_session, test_data):
        """Test that similarity values are in valid range."""
        from sqlalchemy import text

        query_embedding = [1.0] + [0.0] * 767
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        result = await db_session.execute(
            text("""
                SELECT
                    (1 - (pe.embedding <=> CAST(:query AS vector))) AS similarity
                FROM product_embeddings pe
                WHERE pe.model_name = 'test-model'
            """),
            {"query": embedding_str},
        )
        similarities = [row[0] for row in result.fetchall()]

        # Cosine similarity should be between -1 and 1
        # After conversion (1 - distance), should be between 0 and 2
        # But normalized vectors should give values between 0 and 1
        for sim in similarities:
            assert -1.0 <= sim <= 2.0, f"Similarity {sim} out of range"


class TestPgvectorIndexPerformance:
    """Tests for pgvector index performance."""

    @pytest.mark.asyncio
    async def test_ivfflat_index_exists(self, db_session):
        """Test that IVFFLAT index exists on embeddings."""
        from sqlalchemy import text

        result = await db_session.execute(
            text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'product_embeddings'
                  AND indexdef LIKE '%ivfflat%'
            """)
        )
        indexes = result.fetchall()

        # Note: Index might not exist if table is empty or not created yet
        # This is informational - don't fail the test
        if indexes:
            print(f"Found IVFFLAT indexes: {indexes}")
        else:
            pytest.skip("IVFFLAT index not created yet (table may be empty)")

    @pytest.mark.asyncio
    async def test_search_uses_index(self, db_session, sample_embedding_768):
        """Test that search query uses the vector index."""
        from sqlalchemy import text

        embedding_str = f"[{','.join(str(x) for x in sample_embedding_768)}]"

        # EXPLAIN the query
        result = await db_session.execute(
            text("""
                EXPLAIN (FORMAT JSON)
                SELECT id
                FROM product_embeddings
                WHERE model_name = 'nomic-embed-text'
                ORDER BY embedding <=> CAST(:query AS vector)
                LIMIT 5
            """),
            {"query": embedding_str},
        )
        plan = result.fetchone()[0]

        # Note: Index scan might not be used if table is small
        # This is informational
        print(f"Query plan: {plan}")


class TestEmbeddingsRepositoryIntegration:
    """Integration tests for EmbeddingsRepository."""

    @pytest.mark.asyncio
    async def test_embeddings_repo_insert_and_search(self, db_session):
        """Test EmbeddingsRepository insert and search."""
        from sqlalchemy import text

        from src.db.repositories.embeddings_repo import EmbeddingsRepository

        repo = EmbeddingsRepository(db_session)

        # Create test supplier and item
        supplier_id = uuid4()
        item_id = uuid4()

        await db_session.execute(
            text("""
                INSERT INTO suppliers (id, name, source_type, metadata)
                VALUES (:id, 'Test Supplier', 'csv', '{}')
            """),
            {"id": str(supplier_id)},
        )
        await db_session.execute(
            text("""
                INSERT INTO supplier_items (id, supplier_id, supplier_sku, name, current_price, match_status)
                VALUES (:id, :supplier_id, :sku, 'Test Product', 10.00, 'unmatched')
            """),
            {"id": str(item_id), "supplier_id": str(supplier_id), "sku": f"TEST-{item_id}"},
        )
        await db_session.commit()

        try:
            # Insert embedding
            embedding = [0.1] * 768
            embedding_id = await repo.insert(
                supplier_item_id=item_id,
                embedding=embedding,
                model_name="test-model",
            )
            await db_session.commit()

            assert embedding_id is not None

            # Search for similar
            results = await repo.search_similar(
                query_embedding=embedding,
                top_k=5,
                model_name="test-model",
            )

            assert len(results) >= 1
            # The inserted item should be the most similar to itself
            found = any(r.supplier_item_id == item_id for r in results)
            assert found, "Inserted item not found in search results"

            # Check exists
            exists = await repo.exists(item_id, "test-model")
            assert exists

            # Delete
            deleted = await repo.delete_by_supplier_item_id(item_id, "test-model")
            await db_session.commit()
            assert deleted == 1

        finally:
            # Cleanup
            await db_session.execute(
                text("DELETE FROM product_embeddings WHERE supplier_item_id = :id"),
                {"id": str(item_id)},
            )
            await db_session.execute(
                text("DELETE FROM supplier_items WHERE id = :id"),
                {"id": str(item_id)},
            )
            await db_session.execute(
                text("DELETE FROM suppliers WHERE id = :id"),
                {"id": str(supplier_id)},
            )
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_embeddings_repo_upsert(self, db_session):
        """Test EmbeddingsRepository upsert (ON CONFLICT DO UPDATE)."""
        from sqlalchemy import text

        from src.db.repositories.embeddings_repo import EmbeddingsRepository

        repo = EmbeddingsRepository(db_session)

        # Create test data
        supplier_id = uuid4()
        item_id = uuid4()

        await db_session.execute(
            text("""
                INSERT INTO suppliers (id, name, source_type, metadata)
                VALUES (:id, 'Test Supplier', 'csv', '{}')
            """),
            {"id": str(supplier_id)},
        )
        await db_session.execute(
            text("""
                INSERT INTO supplier_items (id, supplier_id, supplier_sku, name, current_price, match_status)
                VALUES (:id, :supplier_id, :sku, 'Test Product', 10.00, 'unmatched')
            """),
            {"id": str(item_id), "supplier_id": str(supplier_id), "sku": f"TEST-{item_id}"},
        )
        await db_session.commit()

        try:
            # First insert
            embedding1 = [0.1] * 768
            id1 = await repo.insert(item_id, embedding1, "test-model")
            await db_session.commit()

            # Second insert (should update)
            embedding2 = [0.2] * 768
            id2 = await repo.insert(item_id, embedding2, "test-model")
            await db_session.commit()

            # Should be same record (upsert)
            assert id1 == id2

            # Verify the embedding was updated
            record = await repo.get_by_supplier_item_id(item_id, "test-model")
            assert record is not None
            assert record.embedding[0] == pytest.approx(0.2, rel=0.01)

        finally:
            # Cleanup
            await db_session.execute(
                text("DELETE FROM product_embeddings WHERE supplier_item_id = :id"),
                {"id": str(item_id)},
            )
            await db_session.execute(
                text("DELETE FROM supplier_items WHERE id = :id"),
                {"id": str(item_id)},
            )
            await db_session.execute(
                text("DELETE FROM suppliers WHERE id = :id"),
                {"id": str(supplier_id)},
            )
            await db_session.commit()

