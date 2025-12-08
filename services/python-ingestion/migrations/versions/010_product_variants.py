"""Product Variants schema (Phase 10)

Revision ID: 010_product_variants
Revises: 009_semantic_etl_schema
Create Date: 2025-12-07 12:00:00.000000

Adds product variants support:
- product_variants: Links variant instances to base products
- supplier_items.variant_id: FK to specific variant
- Structured variant_attributes for differentiating specs (voltage, capacity, color, etc.)

See: /docs/adr/010-product-variants.md
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010_product_variants'
down_revision: Union[str, None] = '009_semantic_etl_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =====================================================
    # T001: Product Variants Table
    # =====================================================
    # Create product_variants table for grouping product variations
    op.create_table(
        'product_variants',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
            comment='Unique identifier for the variant'
        ),
        sa.Column(
            'product_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('products.id', ondelete='CASCADE'),
            nullable=False,
            comment='Base product this variant belongs to'
        ),
        sa.Column(
            'variant_key',
            sa.String(255),
            nullable=False,
            comment='Human-readable variant identifier, e.g., "48V/20A" or "256GB/Black"'
        ),
        sa.Column(
            'variant_attributes',
            postgresql.JSONB(),
            nullable=False,
            server_default='{}',
            comment='Structured variant attributes, e.g., {"voltage": "48V", "capacity": "20A"}'
        ),
        sa.Column(
            'display_order',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Order for displaying variants in UI (ascending)'
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Creation timestamp'
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Last update timestamp'
        ),
    )
    
    # Unique constraint: one variant key per product
    op.create_unique_constraint(
        'uq_product_variant_key',
        'product_variants',
        ['product_id', 'variant_key']
    )
    
    # Index for product lookups
    op.create_index(
        'idx_product_variants_product',
        'product_variants',
        ['product_id']
    )
    
    # GIN index for JSONB queries on variant_attributes
    op.create_index(
        'idx_product_variants_attributes',
        'product_variants',
        ['variant_attributes'],
        postgresql_using='gin'
    )
    
    # =====================================================
    # T002: Supplier Items Variant Reference
    # =====================================================
    # Add variant_id to supplier_items for linking to specific variants
    op.add_column(
        'supplier_items',
        sa.Column(
            'variant_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('product_variants.id', ondelete='SET NULL'),
            nullable=True,
            comment='Specific product variant this item represents'
        )
    )
    
    # Index for variant lookups
    op.create_index(
        'idx_supplier_items_variant',
        'supplier_items',
        ['variant_id'],
        postgresql_where=sa.text('variant_id IS NOT NULL')
    )
    
    # =====================================================
    # T003: Products Base Product Flag
    # =====================================================
    # Add has_variants flag to products for quick filtering
    op.add_column(
        'products',
        sa.Column(
            'has_variants',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='True if product has multiple variants'
        )
    )
    
    # Add variant_schema for UI display (which attributes to show)
    op.add_column(
        'products',
        sa.Column(
            'variant_schema',
            postgresql.JSONB(),
            nullable=True,
            comment='Schema of variant attributes, e.g., ["voltage", "capacity"]'
        )
    )
    
    # Index for variant products
    op.create_index(
        'idx_products_has_variants',
        'products',
        ['has_variants'],
        postgresql_where=sa.text('has_variants = true')
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_products_has_variants', 'products')
    op.drop_index('idx_supplier_items_variant', 'supplier_items')
    op.drop_index('idx_product_variants_attributes', 'product_variants')
    op.drop_index('idx_product_variants_product', 'product_variants')
    
    # Drop constraints
    op.drop_constraint('uq_product_variant_key', 'product_variants', type_='unique')
    
    # Drop columns
    op.drop_column('products', 'variant_schema')
    op.drop_column('products', 'has_variants')
    op.drop_column('supplier_items', 'variant_id')
    
    # Drop table
    op.drop_table('product_variants')

