"""Pipeline stabilization schema changes (Phase 11)

Revision ID: 011_pipeline_stabilization
Revises: 010_product_variants
Create Date: 2025-12-09

Adds idempotency, category level enforcement, and duplicate tracking:
- supplier_items.source_row_hash (with index)
- categories.category_level (with backfill + check constraint)
- potential_duplicates table with supporting indexes
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "011_pipeline_stabilization"
down_revision: Union[str, None] = "010_product_variants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =====================================================
    # supplier_items: hash column + index
    # =====================================================
    op.add_column(
        "supplier_items",
        sa.Column(
            "source_row_hash",
            sa.String(length=32),
            nullable=True,
            comment="MD5 hash of normalized source row for idempotent re-ingestion",
        ),
    )
    op.create_index(
        "idx_supplier_items_hash",
        "supplier_items",
        ["source_row_hash"],
    )

    # =====================================================
    # categories: category_level + backfill + constraint
    # =====================================================
    op.add_column(
        "categories",
        sa.Column(
            "category_level",
            sa.Integer(),
            nullable=True,
            comment="Hierarchy level (1=Top, 2=Sub, 3=Brand)",
        ),
    )

    # Backfill category levels using a recursive CTE, capped at 3 levels
    op.execute(
        sa.text(
            """
            WITH RECURSIVE cat_levels AS (
                SELECT id, parent_id, 1 AS level
                FROM categories
                WHERE parent_id IS NULL

                UNION ALL

                SELECT c.id, c.parent_id, cat_levels.level + 1
                FROM categories c
                JOIN cat_levels ON c.parent_id = cat_levels.id
            )
            UPDATE categories AS c
            SET category_level = LEAST(cl.level, 3)
            FROM cat_levels cl
            WHERE c.id = cl.id;
            """
        )
    )

    # Enforce NOT NULL after backfill
    op.alter_column("categories", "category_level", nullable=False)

    # Check constraint for allowed levels
    op.create_check_constraint(
        "chk_category_level",
        "categories",
        "category_level IN (1, 2, 3)",
    )

    # =====================================================
    # potential_duplicates table
    # =====================================================
    op.create_table(
        "potential_duplicates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique identifier for the duplicate pair",
        ),
        sa.Column(
            "product_id_1",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="First product in the suspected duplicate pair",
        ),
        sa.Column(
            "product_id_2",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Second product in the suspected duplicate pair",
        ),
        sa.Column(
            "similarity_score",
            sa.Numeric(5, 2),
            nullable=False,
            comment="Name similarity score (0-100)",
        ),
        sa.Column(
            "detection_reason",
            sa.String(length=100),
            nullable=False,
            comment="Why this pair was flagged (e.g., auto_creation_similarity)",
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
            comment="pending | merged | dismissed",
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Admin user who reviewed the duplicate",
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the duplicate was reviewed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="When the duplicate was detected",
        ),
        sa.ForeignKeyConstraint(
            ["product_id_1"],
            ["products.id"],
            ondelete="CASCADE",
            name="fk_potential_duplicates_product_1",
        ),
        sa.ForeignKeyConstraint(
            ["product_id_2"],
            ["products.id"],
            ondelete="CASCADE",
            name="fk_potential_duplicates_product_2",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name="fk_potential_duplicates_reviewed_by",
        ),
        sa.CheckConstraint(
            "product_id_1 != product_id_2",
            name="chk_different_products",
        ),
        sa.CheckConstraint(
            "product_id_1 < product_id_2",
            name="chk_ordered_ids",
        ),
        sa.CheckConstraint(
            "similarity_score BETWEEN 0 AND 100",
            name="chk_similarity_range",
        ),
    )

    op.create_index(
        "idx_potential_duplicates_status",
        "potential_duplicates",
        ["status"],
    )
    op.create_index(
        "idx_potential_duplicates_product1",
        "potential_duplicates",
        ["product_id_1"],
    )
    op.create_index(
        "idx_potential_duplicates_product2",
        "potential_duplicates",
        ["product_id_2"],
    )


def downgrade() -> None:
    # Drop potential_duplicates indexes then table
    op.drop_index("idx_potential_duplicates_product2", table_name="potential_duplicates")
    op.drop_index("idx_potential_duplicates_product1", table_name="potential_duplicates")
    op.drop_index("idx_potential_duplicates_status", table_name="potential_duplicates")
    op.drop_table("potential_duplicates")

    # Remove category level constraint and column
    op.drop_constraint("chk_category_level", "categories", type_="check")
    op.drop_column("categories", "category_level")

    # Remove source_row_hash column and index
    op.drop_index("idx_supplier_items_hash", table_name="supplier_items")
    op.drop_column("supplier_items", "source_row_hash")
