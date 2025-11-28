"""Initial schema with all tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-11-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create product_status enum
    product_status_enum = postgresql.ENUM('draft', 'active', 'archived', name='product_status', create_type=True)
    product_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create suppliers table
    op.create_table(
        'suppliers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("source_type IN ('google_sheets', 'csv', 'excel')", name='check_source_type')
    )
    op.create_index('idx_suppliers_source_type', 'suppliers', ['source_type'])
    op.create_index('idx_suppliers_name', 'suppliers', ['name'])
    
    # Create categories table
    op.create_table(
        'categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('name', 'parent_id', name='uq_category_name_parent')
    )
    op.create_index('idx_categories_parent', 'categories', ['parent_id'])
    
    # Create products table
    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('internal_sku', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', postgresql.ENUM('draft', 'active', 'archived', name='product_status', create_type=False), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('internal_sku', name='products_internal_sku_key')
    )
    op.create_index('idx_products_category', 'products', ['category_id'])
    op.create_index('idx_products_status', 'products', ['status'])
    op.create_index('idx_products_name', 'products', ['name'], postgresql_ops={'name': 'varchar_pattern_ops'})
    op.create_index('idx_products_sku', 'products', ['internal_sku'])
    
    # Create supplier_items table
    op.create_table(
        'supplier_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('supplier_sku', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('current_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('characteristics', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('last_ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('supplier_id', 'supplier_sku', name='unique_supplier_sku'),
        sa.CheckConstraint('current_price >= 0', name='check_positive_price')
    )
    op.create_index('idx_supplier_items_supplier', 'supplier_items', ['supplier_id'])
    op.create_index('idx_supplier_items_product', 'supplier_items', ['product_id'])
    op.create_index('idx_supplier_items_characteristics', 'supplier_items', ['characteristics'], postgresql_using='gin')
    op.create_index('idx_supplier_items_price', 'supplier_items', ['current_price'])
    op.create_index('idx_supplier_items_last_ingested', 'supplier_items', ['last_ingested_at'], postgresql_ops={'last_ingested_at': 'DESC'})
    
    # Create price_history table
    op.create_table(
        'price_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('supplier_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['supplier_item_id'], ['supplier_items.id'], ondelete='CASCADE'),
        sa.CheckConstraint('price >= 0', name='check_positive_price')
    )
    op.create_index('idx_price_history_item', 'price_history', ['supplier_item_id'])
    op.create_index('idx_price_history_recorded', 'price_history', ['recorded_at'], postgresql_ops={'recorded_at': 'DESC'})
    op.create_index('idx_price_history_item_recorded', 'price_history', ['supplier_item_id', 'recorded_at'], postgresql_ops={'recorded_at': 'DESC'})
    
    # Create parsing_logs table
    op.create_table(
        'parsing_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', sa.String(length=255), nullable=False),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('error_type', sa.String(length=100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=True),
        sa.Column('row_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='SET NULL')
    )
    op.create_index('idx_parsing_logs_supplier', 'parsing_logs', ['supplier_id'])
    op.create_index('idx_parsing_logs_task', 'parsing_logs', ['task_id'])
    op.create_index('idx_parsing_logs_created', 'parsing_logs', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_parsing_logs_error_type', 'parsing_logs', ['error_type'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('parsing_logs')
    op.drop_table('price_history')
    op.drop_table('supplier_items')
    op.drop_table('products')
    op.drop_table('categories')
    op.drop_table('suppliers')
    
    # Drop enum
    product_status_enum = postgresql.ENUM('draft', 'active', 'archived', name='product_status')
    product_status_enum.drop(op.get_bind(), checkfirst=True)

