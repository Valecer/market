"""Semantic ETL schema additions (Phase 9)

Revision ID: 009_semantic_etl_schema
Revises: 008_create_product_embeddings
Create Date: 2025-12-04 12:00:00.000000

Adds columns for semantic ETL pipeline:
- categories: needs_review, is_active, supplier_id, updated_at
- suppliers: use_semantic_etl feature flag
- parsing_logs: chunk_id, extraction_phase enhancements
- supplier_items: price_opt, price_rrc (semantic pricing columns)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '009_semantic_etl_schema'
down_revision: Union[str, None] = '008_create_product_embeddings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =====================================================
    # T001: Category Hierarchy Enhancements
    # =====================================================
    # Add needs_review column for category governance
    op.add_column(
        'categories',
        sa.Column(
            'needs_review',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Flag for admin review queue (semantic ETL)'
        )
    )
    
    # Add is_active column for soft delete
    op.add_column(
        'categories',
        sa.Column(
            'is_active',
            sa.Boolean(),
            nullable=False,
            server_default='true',
            comment='Soft delete flag'
        )
    )
    
    # Add supplier_id to track category origin
    op.add_column(
        'categories',
        sa.Column(
            'supplier_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('suppliers.id', ondelete='SET NULL'),
            nullable=True,
            comment='Original supplier that created this category'
        )
    )
    
    # Add updated_at timestamp
    op.add_column(
        'categories',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Last update timestamp'
        )
    )
    
    # Create indexes for category governance queries
    op.create_index(
        'idx_categories_needs_review',
        'categories',
        ['needs_review'],
        postgresql_where=sa.text('needs_review = true')
    )
    
    op.create_index(
        'idx_categories_supplier_id',
        'categories',
        ['supplier_id'],
        postgresql_where=sa.text('supplier_id IS NOT NULL')
    )
    
    op.create_index(
        'idx_categories_is_active',
        'categories',
        ['is_active'],
        postgresql_where=sa.text('is_active = true')
    )
    
    # Add constraint: prevent circular references
    op.create_check_constraint(
        'chk_no_self_reference',
        'categories',
        'id != parent_id'
    )
    
    # =====================================================
    # T002: Supplier Items Price Columns
    # =====================================================
    # Add price_opt (wholesale/optimal price)
    op.add_column(
        'supplier_items',
        sa.Column(
            'price_opt',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment='Wholesale/optimal price in BYN'
        )
    )
    
    # Add price_rrc (retail/recommended price)
    op.add_column(
        'supplier_items',
        sa.Column(
            'price_rrc',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment='Retail/recommended price in BYN'
        )
    )
    
    # Add category_id to supplier_items for direct category linking
    op.add_column(
        'supplier_items',
        sa.Column(
            'category_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('categories.id', ondelete='SET NULL'),
            nullable=True,
            comment='Direct category reference from semantic ETL'
        )
    )
    
    # Add constraints for price validation
    op.create_check_constraint(
        'chk_price_opt_positive',
        'supplier_items',
        'price_opt IS NULL OR price_opt >= 0'
    )
    
    op.create_check_constraint(
        'chk_price_rrc_positive',
        'supplier_items',
        'price_rrc IS NULL OR price_rrc >= 0'
    )
    
    # Create index for category lookup
    op.create_index(
        'idx_supplier_items_category',
        'supplier_items',
        ['category_id'],
        postgresql_where=sa.text('category_id IS NOT NULL')
    )
    
    # =====================================================
    # T003: Parsing Logs Enhancement
    # =====================================================
    # Add chunk_id for sliding window tracking
    op.add_column(
        'parsing_logs',
        sa.Column(
            'chunk_id',
            sa.Integer(),
            nullable=True,
            comment='Chunk identifier for sliding window extraction'
        )
    )
    
    # Add extraction_phase for semantic ETL phase tracking
    op.add_column(
        'parsing_logs',
        sa.Column(
            'extraction_phase',
            sa.String(50),
            nullable=True,
            comment='Phase: sheet_selection, markdown_conversion, llm_extraction, category_matching'
        )
    )
    
    # Create index for phase-based error queries
    op.create_index(
        'idx_parsing_logs_extraction_phase',
        'parsing_logs',
        ['extraction_phase'],
        postgresql_where=sa.text('extraction_phase IS NOT NULL')
    )
    
    # =====================================================
    # T007: Suppliers Feature Flag
    # =====================================================
    # Add use_semantic_etl feature flag
    op.add_column(
        'suppliers',
        sa.Column(
            'use_semantic_etl',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Enable semantic ETL for this supplier'
        )
    )
    
    # Create index for feature flag queries
    op.create_index(
        'idx_suppliers_use_semantic_etl',
        'suppliers',
        ['use_semantic_etl'],
        postgresql_where=sa.text('use_semantic_etl = true')
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_suppliers_use_semantic_etl', 'suppliers')
    op.drop_index('idx_parsing_logs_extraction_phase', 'parsing_logs')
    op.drop_index('idx_supplier_items_category', 'supplier_items')
    op.drop_index('idx_categories_is_active', 'categories')
    op.drop_index('idx_categories_supplier_id', 'categories')
    op.drop_index('idx_categories_needs_review', 'categories')
    
    # Drop constraints
    op.drop_constraint('chk_price_rrc_positive', 'supplier_items', type_='check')
    op.drop_constraint('chk_price_opt_positive', 'supplier_items', type_='check')
    op.drop_constraint('chk_no_self_reference', 'categories', type_='check')
    
    # Drop columns
    op.drop_column('suppliers', 'use_semantic_etl')
    op.drop_column('parsing_logs', 'extraction_phase')
    op.drop_column('parsing_logs', 'chunk_id')
    op.drop_column('supplier_items', 'category_id')
    op.drop_column('supplier_items', 'price_rrc')
    op.drop_column('supplier_items', 'price_opt')
    op.drop_column('categories', 'updated_at')
    op.drop_column('categories', 'supplier_id')
    op.drop_column('categories', 'is_active')
    op.drop_column('categories', 'needs_review')

