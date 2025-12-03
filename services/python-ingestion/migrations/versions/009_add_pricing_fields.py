"""Add retail_price, wholesale_price, and currency_code to products.

This migration adds canonical pricing fields to support dual pricing
(retail/wholesale) with currency tracking.

Revision ID: 009_add_pricing_fields
Revises: 008_create_product_embeddings
Create Date: 2025-12-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '009_add_pricing_fields'
down_revision: Union[str, None] = '008_create_product_embeddings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pricing columns and constraints to products table."""
    # Add retail_price column (nullable, no default)
    op.add_column(
        'products',
        sa.Column('retail_price', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    
    # Add wholesale_price column (nullable, no default)
    op.add_column(
        'products',
        sa.Column('wholesale_price', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    
    # Add currency_code column (nullable, no default)
    op.add_column(
        'products',
        sa.Column('currency_code', sa.String(length=3), nullable=True)
    )
    
    # Add check constraint for retail_price >= 0
    op.create_check_constraint(
        'check_retail_price_non_negative',
        'products',
        'retail_price IS NULL OR retail_price >= 0'
    )
    
    # Add check constraint for wholesale_price >= 0
    op.create_check_constraint(
        'check_wholesale_price_non_negative',
        'products',
        'wholesale_price IS NULL OR wholesale_price >= 0'
    )


def downgrade() -> None:
    """Remove pricing columns and constraints from products table."""
    # Drop check constraints first
    op.drop_constraint('check_wholesale_price_non_negative', 'products', type_='check')
    op.drop_constraint('check_retail_price_non_negative', 'products', type_='check')
    
    # Drop columns
    op.drop_column('products', 'currency_code')
    op.drop_column('products', 'wholesale_price')
    op.drop_column('products', 'retail_price')

