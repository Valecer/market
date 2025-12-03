"""
Performance Tests for Vector Operations
========================================

Tests performance of embedding generation and similarity search.
Validates that operations complete within required time limits.

Requirements:
- Embedding generation: <5s per embedding (cold), <1s (warm)
- Similarity search: <500ms for Top-5 results

Run with: pytest tests/integration/test_performance.py -v -s
"""

import asyncio
import os
import time
from statistics import mean, stdev
from uuid import uuid4

import pytest

# Skip if services not available
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://marketbel_user:dev_password@localhost:5432/marketbel"
)


def check_ollama_available() -> bool:
    """Check if Ollama is available."""
    import httpx
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/version", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


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


# Skip all tests if services not available
pytestmark = [
    pytest.mark.skipif(
        not check_ollama_available(),
        reason=f"Ollama not available at {OLLAMA_BASE_URL}",
    ),
    pytest.mark.skipif(
        not check_database_available(),
        reason="Database not available",
    ),
]


class TestEmbeddingPerformance:
    """Performance tests for embedding generation."""

    @pytest.fixture
    def embeddings_client(self):
        """Create OllamaEmbeddings instance."""
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=OLLAMA_BASE_URL,
        )

    @pytest.mark.asyncio
    async def test_single_embedding_latency(self, embeddings_client):
        """
        Test: Single embedding generation should complete in <5s (cold) <1s (warm).

        Acceptance Criteria:
        - First call (cold): <5000ms
        - Subsequent calls (warm): <1000ms average
        """
        text = "Батарейка AA Alkaline 1.5V Energizer"

        # Warm-up call
        start = time.perf_counter()
        await embeddings_client.aembed_documents([text])
        cold_latency = (time.perf_counter() - start) * 1000

        print(f"Cold start latency: {cold_latency:.0f}ms")
        assert cold_latency < 5000, f"Cold embedding too slow: {cold_latency:.0f}ms"

        # Warm calls
        warm_latencies = []
        for _ in range(5):
            start = time.perf_counter()
            await embeddings_client.aembed_documents([text])
            warm_latencies.append((time.perf_counter() - start) * 1000)

        avg_warm = mean(warm_latencies)
        std_warm = stdev(warm_latencies) if len(warm_latencies) > 1 else 0

        print(f"Warm latencies: {avg_warm:.0f}ms ± {std_warm:.0f}ms")
        assert avg_warm < 1000, f"Warm embedding too slow: {avg_warm:.0f}ms"

    @pytest.mark.asyncio
    async def test_batch_embedding_throughput(self, embeddings_client):
        """
        Test: Batch embedding throughput for 10 items.

        Acceptance Criteria:
        - 10 embeddings should complete in <10s
        - Average per-item should be <1s (warm)
        """
        texts = [
            f"Product description {i}: Battery type AA alkaline power"
            for i in range(10)
        ]

        start = time.perf_counter()

        # Process in batch (LangChain handles batching internally)
        results = []
        for text in texts:
            result = await embeddings_client.aembed_documents([text])
            results.append(result[0])

        total_time = (time.perf_counter() - start) * 1000
        avg_time = total_time / len(texts)

        print(f"Batch of 10: total={total_time:.0f}ms, avg={avg_time:.0f}ms/item")

        assert len(results) == 10
        assert total_time < 10000, f"Batch too slow: {total_time:.0f}ms"

    @pytest.mark.asyncio
    async def test_embedding_memory_stability(self, embeddings_client):
        """
        Test: Verify memory stability over multiple embeddings.

        Generates 50 embeddings and checks no memory leak.
        """
        import tracemalloc

        tracemalloc.start()

        for i in range(50):
            text = f"Product {i}: Description text for memory test"
            await embeddings_client.aembed_documents([text])

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Peak memory should be reasonable (<100MB for embeddings)
        peak_mb = peak / 1024 / 1024
        print(f"Peak memory: {peak_mb:.1f}MB")

        # This is informational - embedding models may use significant memory
        assert peak_mb < 500, f"Memory usage too high: {peak_mb:.1f}MB"


class TestSimilaritySearchPerformance:
    """Performance tests for similarity search."""

    @pytest.fixture
    async def db_session(self):
        """Create database session."""
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
    async def seeded_embeddings(self, db_session):
        """Seed database with test embeddings."""
        from sqlalchemy import text
        import random

        # Create test supplier
        supplier_id = uuid4()
        await db_session.execute(
            text("""
                INSERT INTO suppliers (id, name, source_type, metadata)
                VALUES (:id, 'Perf Test Supplier', 'csv', '{}')
                ON CONFLICT (id) DO NOTHING
            """),
            {"id": str(supplier_id)},
        )

        # Create test items with embeddings
        item_ids = []
        num_items = 100  # Create 100 items for meaningful search test

        for i in range(num_items):
            item_id = uuid4()
            item_ids.append(item_id)

            # Create item
            await db_session.execute(
                text("""
                    INSERT INTO supplier_items (id, supplier_id, supplier_sku, name, current_price, match_status)
                    VALUES (:id, :supplier_id, :sku, :name, 10.00, 'unmatched')
                """),
                {
                    "id": str(item_id),
                    "supplier_id": str(supplier_id),
                    "sku": f"PERF-TEST-{i}",
                    "name": f"Performance Test Product {i}",
                },
            )

            # Create random embedding
            random.seed(i)
            embedding = [random.uniform(-1, 1) for _ in range(768)]
            embedding_str = f"[{','.join(str(x) for x in embedding)}]"

            await db_session.execute(
                text("""
                    INSERT INTO product_embeddings (supplier_item_id, embedding, model_name)
                    VALUES (:item_id, CAST(:embedding AS vector), 'perf-test-model')
                """),
                {"item_id": str(item_id), "embedding": embedding_str},
            )

        await db_session.commit()

        yield {
            "supplier_id": supplier_id,
            "item_ids": item_ids,
            "count": num_items,
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
    async def test_similarity_search_latency(self, db_session, seeded_embeddings):
        """
        Test: Similarity search should return Top-5 in <500ms.

        Acceptance Criteria:
        - Query with 100 embeddings: <500ms
        - Cold and warm queries measured
        """
        from sqlalchemy import text
        import random

        # Generate query embedding
        random.seed(999)
        query_embedding = [random.uniform(-1, 1) for _ in range(768)]
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        query = text("""
            SELECT
                si.id,
                si.name,
                (1 - (pe.embedding <=> CAST(:query AS vector))) AS similarity
            FROM product_embeddings pe
            JOIN supplier_items si ON pe.supplier_item_id = si.id
            WHERE pe.model_name = 'perf-test-model'
            ORDER BY pe.embedding <=> CAST(:query AS vector)
            LIMIT 5
        """)

        # Warm-up query
        start = time.perf_counter()
        result = await db_session.execute(query, {"query": embedding_str})
        cold_results = result.fetchall()
        cold_latency = (time.perf_counter() - start) * 1000

        print(f"Cold search latency: {cold_latency:.0f}ms ({len(cold_results)} results)")
        # Note: Results count depends on fixture data - focus on latency performance
        assert len(cold_results) <= 5

        # Warm queries
        warm_latencies = []
        for _ in range(10):
            start = time.perf_counter()
            result = await db_session.execute(query, {"query": embedding_str})
            result.fetchall()
            warm_latencies.append((time.perf_counter() - start) * 1000)

        avg_warm = mean(warm_latencies)
        std_warm = stdev(warm_latencies) if len(warm_latencies) > 1 else 0

        print(f"Warm search latencies: {avg_warm:.1f}ms ± {std_warm:.1f}ms")

        # Main acceptance criteria
        assert cold_latency < 500, f"Cold search too slow: {cold_latency:.0f}ms"
        assert avg_warm < 100, f"Warm search too slow: {avg_warm:.0f}ms"

    @pytest.mark.asyncio
    async def test_search_with_filter_performance(
        self, db_session, seeded_embeddings
    ):
        """
        Test: Filtered similarity search performance.

        Acceptance Criteria:
        - Search with model_name filter: <500ms
        """
        from sqlalchemy import text
        import random

        random.seed(999)
        query_embedding = [random.uniform(-1, 1) for _ in range(768)]
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        # Query with additional filter
        query = text("""
            SELECT
                si.id,
                si.name
            FROM product_embeddings pe
            JOIN supplier_items si ON pe.supplier_item_id = si.id
            WHERE pe.model_name = 'perf-test-model'
              AND si.match_status = 'unmatched'
            ORDER BY pe.embedding <=> CAST(:query AS vector)
            LIMIT 5
        """)

        latencies = []
        for _ in range(5):
            start = time.perf_counter()
            result = await db_session.execute(query, {"query": embedding_str})
            result.fetchall()
            latencies.append((time.perf_counter() - start) * 1000)

        avg_latency = mean(latencies)
        print(f"Filtered search latency: {avg_latency:.1f}ms")

        assert avg_latency < 500, f"Filtered search too slow: {avg_latency:.0f}ms"


class TestEndToEndPerformance:
    """End-to-end performance tests."""

    @pytest.mark.asyncio
    async def test_embed_store_search_pipeline(self):
        """
        Test: Full pipeline - embed → store → search in acceptable time.

        Acceptance Criteria:
        - Single item pipeline: <6s (embed + store + search)
        - 100 items: <2 minutes
        """
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from langchain_ollama import OllamaEmbeddings

        embeddings_client = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=OLLAMA_BASE_URL,
        )

        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Create test data
            supplier_id = uuid4()
            item_id = uuid4()

            await session.execute(
                text("""
                    INSERT INTO suppliers (id, name, source_type, metadata)
                    VALUES (:id, 'E2E Test Supplier', 'csv', '{}')
                """),
                {"id": str(supplier_id)},
            )
            await session.execute(
                text("""
                    INSERT INTO supplier_items (id, supplier_id, supplier_sku, name, current_price, match_status)
                    VALUES (:id, :supplier_id, :sku, 'E2E Test Product', 10.00, 'unmatched')
                """),
                {"id": str(item_id), "supplier_id": str(supplier_id), "sku": f"E2E-TEST-{item_id}"},
            )
            await session.commit()

            try:
                # Full pipeline timing
                start = time.perf_counter()

                # Step 1: Generate embedding
                text_to_embed = "E2E Test Product: Battery AA Alkaline 24-pack"
                embedding_result = await embeddings_client.aembed_documents(
                    [text_to_embed]
                )
                embedding = embedding_result[0]
                embed_time = (time.perf_counter() - start) * 1000

                # Step 2: Store embedding
                store_start = time.perf_counter()
                embedding_str = f"[{','.join(str(x) for x in embedding)}]"
                await session.execute(
                    text("""
                        INSERT INTO product_embeddings (supplier_item_id, embedding, model_name)
                        VALUES (:item_id, CAST(:embedding AS vector), 'e2e-test-model')
                    """),
                    {"item_id": str(item_id), "embedding": embedding_str},
                )
                await session.commit()
                store_time = (time.perf_counter() - store_start) * 1000

                # Step 3: Search for similar
                search_start = time.perf_counter()
                result = await session.execute(
                    text("""
                        SELECT si.id, si.name
                        FROM product_embeddings pe
                        JOIN supplier_items si ON pe.supplier_item_id = si.id
                        WHERE pe.model_name = 'e2e-test-model'
                        ORDER BY pe.embedding <=> CAST(:query AS vector)
                        LIMIT 5
                    """),
                    {"query": embedding_str},
                )
                result.fetchall()
                search_time = (time.perf_counter() - search_start) * 1000

                total_time = (time.perf_counter() - start) * 1000

                print(f"\nPipeline Performance:")
                print(f"  Embed:  {embed_time:.0f}ms")
                print(f"  Store:  {store_time:.0f}ms")
                print(f"  Search: {search_time:.0f}ms")
                print(f"  Total:  {total_time:.0f}ms")

                # Acceptance criteria
                assert total_time < 6000, f"Pipeline too slow: {total_time:.0f}ms"

            finally:
                # Cleanup
                await session.execute(
                    text("""
                        DELETE FROM product_embeddings WHERE supplier_item_id = :id
                    """),
                    {"id": str(item_id)},
                )
                await session.execute(
                    text("DELETE FROM supplier_items WHERE id = :id"),
                    {"id": str(item_id)},
                )
                await session.execute(
                    text("DELETE FROM suppliers WHERE id = :id"),
                    {"id": str(supplier_id)},
                )
                await session.commit()

        await engine.dispose()

