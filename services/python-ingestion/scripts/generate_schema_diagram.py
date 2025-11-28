#!/usr/bin/env python3
"""Generate database schema diagram (ERD) for data ingestion infrastructure.

This script generates a visual representation of the database schema using
the erdantic library or creates a text-based ERD.

Requirements:
    pip install erdantic graphviz

Usage:
    python scripts/generate_schema_diagram.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import graphviz
    
    def generate_graphviz_diagram():
        """Generate ERD using Graphviz directly."""
        # Create a new directed graph
        dot = graphviz.Digraph(comment='Database Schema', format='png')
        dot.attr(rankdir='TB', size='12,16')
        dot.attr('node', shape='record', style='rounded')
        
        # Define tables with their columns
        dot.node('suppliers', '''{SUPPLIERS|id (UUID, PK)\\nname (VARCHAR(255))\\nsource_type (VARCHAR(50))\\ncontact_email (VARCHAR(255))\\nmetadata (JSONB)\\ncreated_at (TIMESTAMP)\\nupdated_at (TIMESTAMP)}''')
        
        dot.node('supplier_items', '''{SUPPLIER_ITEMS|id (UUID, PK)\\nsupplier_id (UUID, FK)\\nproduct_id (UUID, FK)\\nsupplier_sku (VARCHAR(255))\\nname (VARCHAR(500))\\ncurrent_price (NUMERIC(10,2))\\ncharacteristics (JSONB)\\nlast_ingested_at (TIMESTAMP)\\ncreated_at (TIMESTAMP)\\nupdated_at (TIMESTAMP)}''')
        
        dot.node('products', '''{PRODUCTS|id (UUID, PK)\\ninternal_sku (VARCHAR(100), UNIQUE)\\nname (VARCHAR(500))\\ncategory_id (UUID, FK)\\nstatus (ENUM)\\ncreated_at (TIMESTAMP)\\nupdated_at (TIMESTAMP)}''')
        
        dot.node('categories', '''{CATEGORIES|id (UUID, PK)\\nname (VARCHAR(255))\\nparent_id (UUID, FK)\\ncreated_at (TIMESTAMP)}''')
        
        dot.node('price_history', '''{PRICE_HISTORY|id (UUID, PK)\\nsupplier_item_id (UUID, FK)\\nprice (NUMERIC(10,2))\\nrecorded_at (TIMESTAMP)}''')
        
        dot.node('parsing_logs', '''{PARSING_LOGS|id (UUID, PK)\\ntask_id (VARCHAR(255))\\nsupplier_id (UUID, FK)\\nerror_type (VARCHAR(100))\\nerror_message (TEXT)\\nrow_number (INTEGER)\\nrow_data (JSONB)\\ncreated_at (TIMESTAMP)}''')
        
        # Define relationships
        dot.edge('suppliers', 'supplier_items', label='1:N\\nCASCADE DELETE')
        dot.edge('supplier_items', 'price_history', label='1:N\\nCASCADE DELETE')
        dot.edge('products', 'supplier_items', label='1:N\\nSET NULL')
        dot.edge('categories', 'products', label='1:N\\nSET NULL')
        dot.edge('categories', 'categories', label='Self-ref\\nCASCADE DELETE', style='dashed')
        dot.edge('suppliers', 'parsing_logs', label='1:N\\nSET NULL')
        
        # Save to file
        output_path = project_root.parent.parent / "docs" / "schema-diagram"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Render the diagram
        dot.render(output_path, format='png', cleanup=True)
        
        print(f"✓ ERD diagram saved to: {output_path}.png")
        return True

except ImportError:
    print("graphviz not installed. Creating text-based ERD instead...")
    
    def generate_text_erd():
        """Generate text-based ERD."""
        erd_text = """
Database Schema: Data Ingestion Infrastructure
==============================================

┌─────────────────────────────────────────────────────────────┐
│                        SUPPLIERS                            │
├─────────────────────────────────────────────────────────────┤
│ id (UUID, PK)                                               │
│ name (VARCHAR(255), NOT NULL, INDEX)                        │
│ source_type (VARCHAR(50), NOT NULL, INDEX)                  │
│   CHECK: source_type IN ('google_sheets', 'csv', 'excel')  │
│ contact_email (VARCHAR(255), NULL)                           │
│ metadata (JSONB, NOT NULL, DEFAULT '{}')                    │
│ created_at (TIMESTAMP, NOT NULL)                            │
│ updated_at (TIMESTAMP, NOT NULL)                             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ 1:N (CASCADE DELETE)
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                     SUPPLIER_ITEMS                          │
├─────────────────────────────────────────────────────────────┤
│ id (UUID, PK)                                               │
│ supplier_id (UUID, FK → suppliers.id, NOT NULL, INDEX)      │
│ product_id (UUID, FK → products.id, NULL, INDEX)             │
│ supplier_sku (VARCHAR(255), NOT NULL)                       │
│ name (VARCHAR(500), NOT NULL)                               │
│ current_price (NUMERIC(10,2), NOT NULL, INDEX)               │
│   CHECK: current_price >= 0                                 │
│ characteristics (JSONB, NOT NULL, DEFAULT '{}', GIN INDEX)  │
│ last_ingested_at (TIMESTAMP, NOT NULL, INDEX DESC)          │
│ created_at (TIMESTAMP, NOT NULL)                            │
│ updated_at (TIMESTAMP, NOT NULL)                            │
│ UNIQUE(supplier_id, supplier_sku)                          │
└───────┬───────────────────────────────┬─────────────────────┘
        │                               │
        │ 1:N (CASCADE DELETE)          │ N:1 (SET NULL)
        │                               │
        ▼                               ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│     PRICE_HISTORY         │  │         PRODUCTS               │
├──────────────────────────┤  ├──────────────────────────────┤
│ id (UUID, PK)            │  │ id (UUID, PK)                 │
│ supplier_item_id (UUID,  │  │ internal_sku (VARCHAR(100),   │
│   FK → supplier_items.id,│  │   UNIQUE, NOT NULL, INDEX)    │
│   NOT NULL, INDEX)       │  │ name (VARCHAR(500), NOT NULL,  │
│ price (NUMERIC(10,2),    │  │   INDEX)                       │
│   NOT NULL)              │  │ category_id (UUID, FK →        │
│   CHECK: price >= 0      │  │   categories.id, NULL, INDEX)  │
│ recorded_at (TIMESTAMP,   │  │ status (ENUM, NOT NULL,        │
│   NOT NULL, INDEX DESC)  │  │   DEFAULT 'draft', INDEX)      │
│                          │  │   VALUES: draft/active/archived│
└──────────────────────────┘  │ created_at (TIMESTAMP)        │
                              │ updated_at (TIMESTAMP)          │
                              └──────────────┬─────────────────┘
                                             │
                                             │ N:1 (SET NULL)
                                             │
                                             ▼
                              ┌──────────────────────────────┐
                              │        CATEGORIES              │
                              ├──────────────────────────────┤
                              │ id (UUID, PK)                 │
                              │ name (VARCHAR(255), NOT NULL)  │
                              │ parent_id (UUID, FK →         │
                              │   categories.id, NULL, INDEX) │
                              │   (Self-referential)           │
                              │ created_at (TIMESTAMP)         │
                              │ UNIQUE(name, parent_id)        │
                              └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      PARSING_LOGS                           │
├─────────────────────────────────────────────────────────────┤
│ id (UUID, PK)                                               │
│ task_id (VARCHAR(255), NOT NULL, INDEX)                      │
│ supplier_id (UUID, FK → suppliers.id, NULL, INDEX)           │
│   ON DELETE SET NULL                                         │
│ error_type (VARCHAR(100), NOT NULL, INDEX)                   │
│ error_message (TEXT, NOT NULL)                               │
│ row_number (INTEGER, NULL)                                   │
│ row_data (JSONB, NULL)                                       │
│ created_at (TIMESTAMP, NOT NULL, INDEX DESC)                 │
└─────────────────────────────────────────────────────────────┘

Key Relationships:
------------------
1. Supplier → SupplierItems (1:N, CASCADE DELETE)
   - Deleting a supplier deletes all its items

2. SupplierItem → PriceHistory (1:N, CASCADE DELETE)
   - Deleting a supplier item deletes its price history

3. Product → SupplierItems (1:N, SET NULL)
   - Deleting a product sets supplier_items.product_id to NULL

4. Category → Products (1:N, SET NULL)
   - Deleting a category sets products.category_id to NULL

5. Category → Categories (Self-referential, CASCADE DELETE)
   - Deleting a parent category deletes all child categories

6. Supplier → ParsingLogs (1:N, SET NULL)
   - Deleting a supplier sets parsing_logs.supplier_id to NULL

Key Indexes:
------------
- GIN index on supplier_items.characteristics (JSONB queries)
- Composite unique index on (supplier_id, supplier_sku)
- Descending indexes on timestamp columns for chronological queries
- Indexes on foreign keys for join performance
"""
        
        output_path = project_root.parent.parent / "docs" / "schema-diagram.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(erd_text)
        
        print(f"✓ Text-based ERD saved to: {output_path}")
        print("\nTo generate a visual diagram, install erdantic:")
        print("  pip install erdantic graphviz")
        return True


if __name__ == "__main__":
    try:
        # Try to use graphviz if available
        if 'generate_graphviz_diagram' in globals():
            generate_graphviz_diagram()
        else:
            generate_text_erd()
    except Exception as e:
        print(f"Error generating diagram: {e}")
        print("Falling back to text-based ERD...")
        if 'generate_text_erd' in globals():
            generate_text_erd()
        else:
            print("Could not generate diagram. Please check dependencies.")

