"""Add matching pipeline tables and columns.

This migration adds:
- match_status ENUM type for supplier items
- review_status ENUM type for review queue
- Aggregate columns (min_price, availability, mrp) to products table
- Matching columns (match_status, match_score, match_candidates) to supplier_items
- match_review_queue table with indexes

Revision ID: 002_add_matching_pipeline
Revises: 001_initial_schema
Create Date: 2025-11-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_matching_pipeline'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===== T010: Create ENUM types =====
    
    # Create match_status enum type
    match_status_enum = postgresql.ENUM(
        'unmatched',
        'auto_matched',
        'potential_match',
        'verified_match',
        name='match_status',
        create_type=True
    )
    match_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create review_status enum type
    review_status_enum = postgresql.ENUM(
        'pending',
        'approved',
        'rejected',
        'expired',
        'needs_category',
        name='review_status',
        create_type=True
    )
    review_status_enum.create(op.get_bind(), checkfirst=True)
    
    # ===== T011: Add aggregate columns to products table =====
    
    op.add_column(
        'products',
        sa.Column('min_price', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    op.add_column(
        'products',
        sa.Column('availability', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'products',
        sa.Column('mrp', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    
    # ===== T012: Add matching columns to supplier_items table =====
    
    op.add_column(
        'supplier_items',
        sa.Column(
            'match_status',
            postgresql.ENUM(
                'unmatched',
                'auto_matched',
                'potential_match',
                'verified_match',
                name='match_status',
                create_type=False
            ),
            nullable=False,
            server_default='unmatched'
        )
    )
    op.add_column(
        'supplier_items',
        sa.Column('match_score', sa.Numeric(precision=5, scale=2), nullable=True)
    )
    op.add_column(
        'supplier_items',
        sa.Column('match_candidates', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    
    # Add constraint for match_score range (0-100)
    op.create_check_constraint(
        'check_match_score',
        'supplier_items',
        'match_score IS NULL OR (match_score >= 0 AND match_score <= 100)'
    )
    
    # ===== T013: Create match_review_queue table =====
    
    op.create_table(
        'match_review_queue',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()')
        ),
        sa.Column(
            'supplier_item_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('supplier_items.id', ondelete='CASCADE'),
            nullable=False,
            unique=True
        ),
        sa.Column(
            'candidate_products',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='[]'
        ),
        sa.Column(
            'status',
            postgresql.ENUM(
                'pending',
                'approved',
                'rejected',
                'expired',
                'needs_category',
                name='review_status',
                create_type=False
            ),
            nullable=False,
            server_default='pending'
        ),
        sa.Column(
            'reviewed_by',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True
        ),
        sa.Column(
            'reviewed_at',
            sa.DateTime(timezone=True),
            nullable=True
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()')
        ),
        sa.Column(
            'expires_at',
            sa.DateTime(timezone=True),
            nullable=False
        ),
    )
    
    # ===== T014: Create indexes =====
    
    # Products table indexes
    op.create_index(
        'idx_products_min_price',
        'products',
        ['min_price'],
        postgresql_where=sa.text('min_price IS NOT NULL')
    )
    op.create_index(
        'idx_products_availability',
        'products',
        ['availability']
    )
    
    # Supplier items table indexes
    op.create_index(
        'idx_supplier_items_match_status',
        'supplier_items',
        ['match_status']
    )
    op.create_index(
        'idx_supplier_items_unmatched',
        'supplier_items',
        ['product_id'],
        postgresql_where=sa.text("product_id IS NULL AND match_status = 'unmatched'")
    )
    op.create_index(
        'idx_supplier_items_match_score',
        'supplier_items',
        [sa.text('match_score DESC')],
        postgresql_where=sa.text('match_score IS NOT NULL')
    )
    
    # Match review queue table indexes
    op.create_index(
        'idx_review_queue_status',
        'match_review_queue',
        ['status']
    )
    op.create_index(
        'idx_review_queue_expires',
        'match_review_queue',
        ['expires_at'],
        postgresql_where=sa.text("status = 'pending'")
    )
    op.create_index(
        'idx_review_queue_created',
        'match_review_queue',
        [sa.text('created_at DESC')]
    )
    op.create_index(
        'idx_review_queue_status_expires',
        'match_review_queue',
        ['status', 'expires_at'],
        postgresql_where=sa.text("status = 'pending'")
    )


def downgrade() -> None:
    # ===== Drop match_review_queue table and indexes =====
    op.drop_index('idx_review_queue_status_expires', table_name='match_review_queue')
    op.drop_index('idx_review_queue_created', table_name='match_review_queue')
    op.drop_index('idx_review_queue_expires', table_name='match_review_queue')
    op.drop_index('idx_review_queue_status', table_name='match_review_queue')
    op.drop_table('match_review_queue')
    
    # ===== Drop supplier_items columns and indexes =====
    op.drop_index('idx_supplier_items_match_score', table_name='supplier_items')
    op.drop_index('idx_supplier_items_unmatched', table_name='supplier_items')
    op.drop_index('idx_supplier_items_match_status', table_name='supplier_items')
    op.drop_constraint('check_match_score', 'supplier_items', type_='check')
    op.drop_column('supplier_items', 'match_candidates')
    op.drop_column('supplier_items', 'match_score')
    op.drop_column('supplier_items', 'match_status')
    
    # ===== Drop products columns and indexes =====
    op.drop_index('idx_products_availability', table_name='products')
    op.drop_index('idx_products_min_price', table_name='products')
    op.drop_column('products', 'mrp')
    op.drop_column('products', 'availability')
    op.drop_column('products', 'min_price')
    
    # ===== Drop ENUM types =====
    review_status_enum = postgresql.ENUM(
        'pending',
        'approved',
        'rejected',
        'expired',
        'needs_category',
        name='review_status'
    )
    review_status_enum.drop(op.get_bind(), checkfirst=True)
    
    match_status_enum = postgresql.ENUM(
        'unmatched',
        'auto_matched',
        'potential_match',
        'verified_match',
        name='match_status'
    )
    match_status_enum.drop(op.get_bind(), checkfirst=True)

