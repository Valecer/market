"""Enable pgvector extension for vector similarity search

Revision ID: 007_enable_pgvector
Revises: 002_add_matching_pipeline
Create Date: 2025-12-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '007_enable_pgvector'
down_revision: Union[str, None] = '002_add_matching_pipeline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pgvector extension in PostgreSQL."""
    # Enable the vector extension for vector similarity search
    # This is idempotent - safe to run multiple times
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Disable pgvector extension."""
    # Note: This will fail if product_embeddings table still exists
    # Drop the table first or use CASCADE (not recommended)
    op.execute("DROP EXTENSION IF EXISTS vector")

