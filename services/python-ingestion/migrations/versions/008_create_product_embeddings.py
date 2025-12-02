"""Create product_embeddings table for vector similarity search

Revision ID: 008_create_product_embeddings
Revises: 007_enable_pgvector
Create Date: 2025-12-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '008_create_product_embeddings'
down_revision: Union[str, None] = '007_enable_pgvector'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create product_embeddings table with vector column and indexes."""
    # Create table
    op.execute("""
        CREATE TABLE IF NOT EXISTS product_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            supplier_item_id UUID NOT NULL REFERENCES supplier_items(id) ON DELETE CASCADE,
            embedding vector(768),
            model_name VARCHAR(100) NOT NULL DEFAULT 'nomic-embed-text',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT unique_item_model_embedding UNIQUE (supplier_item_id, model_name)
        )
    """)

    # Create IVFFLAT index for fast cosine similarity search
    # lists parameter = sqrt(expected rows), start with 100 for ~10k products
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_cosine_similarity
        ON product_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Create index on supplier_item_id for faster lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_supplier_item_id
        ON product_embeddings (supplier_item_id)
    """)

    # Create index on model_name for filtering by model
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_model_name
        ON product_embeddings (model_name)
    """)

    # Add comment to table for documentation
    op.execute("""
        COMMENT ON TABLE product_embeddings IS
        'Vector embeddings for supplier items, used for semantic similarity search in product matching (Phase 7 ml-analyze)'
    """)


def downgrade() -> None:
    """Drop product_embeddings table and indexes."""
    op.execute("DROP INDEX IF EXISTS idx_embeddings_model_name")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_supplier_item_id")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_cosine_similarity")
    op.execute("DROP TABLE IF EXISTS product_embeddings")

