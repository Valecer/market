# Google Sheets Test Parsing Guide

This guide explains how to parse product data from Google Sheets into the Marketbel catalog for testing purposes.

## Prerequisites

1. **Docker services running:**
   ```bash
   docker-compose up -d
   ```

2. **Google Sheets credentials configured:**
   - Service account credentials at `credentials/google-credentials.json`
   - Google Sheet shared with the service account email

3. **Verify authentication:**
   ```bash
   docker-compose exec worker python -c "
   import gspread
   client = gspread.service_account(filename='/app/credentials/google-credentials.json')
   print('✅ Google Sheets authentication successful!')
   "
   ```

## Google Sheet Format

Your Google Sheet should have columns that can be mapped to:

| Required Field | Example Column Names |
|----------------|---------------------|
| SKU | `Product Code`, `Item Code`, `SKU` |
| Name | `Product Name`, `Description`, `Name` |
| Price | `Unit Price`, `Price`, `Cost` |

Additional columns become **characteristics** (stored as JSONB):
- Color, Size, Material, Weight, etc.

### Example Sheet Structure

| Product Code | Product Name | Unit Price | Color | Size | Material |
|-------------|--------------|------------|-------|------|----------|
| TEST-0001 | Wool Sweater | 100.71 | Blue | XS | 100% Wool |
| TEST-0002 | Cotton T-Shirt | 25.99 | Red | M | 100% Cotton |

## Step-by-Step Instructions

### Step 1: Check Sheet Columns

Verify your sheet structure before parsing:

```bash
docker-compose exec worker python -c "
import gspread
client = gspread.service_account(filename='/app/credentials/google-credentials.json')
sheet = client.open_by_url('YOUR_GOOGLE_SHEET_URL')
worksheet = sheet.sheet1
headers = worksheet.row_values(1)
print('Column headers:')
for i, h in enumerate(headers, 1):
    print(f'  {i}. {h}')
"
```

### Step 2: Create a Supplier

```bash
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "
INSERT INTO suppliers (id, name, source_type, metadata)
VALUES (
    gen_random_uuid(),
    'YOUR_SUPPLIER_NAME',
    'google_sheets',
    '{\"spreadsheet_url\": \"YOUR_GOOGLE_SHEET_URL\", \"sheet_name\": \"Sheet1\"}'
)
RETURNING id, name;
"
```

**Save the returned supplier ID for later use.**

### Step 3: Enqueue Parsing Task

```bash
cd services/python-ingestion

docker-compose -f ../../docker-compose.yml exec worker python scripts/enqueue_task.py \
  --task-id "test-$(date +%s)" \
  --parser-type google_sheets \
  --supplier-name "YOUR_SUPPLIER_NAME" \
  --sheet-url "YOUR_GOOGLE_SHEET_URL" \
  --sheet-name "Sheet1"
```

### Step 4: Monitor Parsing Progress

```bash
# Watch worker logs
docker-compose logs -f worker

# Check parsed items count
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "
SELECT COUNT(*) as items FROM supplier_items 
WHERE supplier_id IN (SELECT id FROM suppliers WHERE name = 'YOUR_SUPPLIER_NAME');
"
```

### Step 5: Create Products from Supplier Items

Products are created from supplier items and aggregated by name:

```bash
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "
-- Create products from supplier items
INSERT INTO products (id, internal_sku, name, status, created_at, updated_at)
SELECT 
    gen_random_uuid(),
    'PRD-' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT) FROM 1 FOR 8)),
    si.name,
    'active',
    NOW(),
    NOW()
FROM supplier_items si
JOIN suppliers s ON si.supplier_id = s.id
WHERE s.name = 'YOUR_SUPPLIER_NAME'
  AND si.product_id IS NULL;

-- Link supplier items to products
WITH matched AS (
    SELECT 
        si.id as si_id,
        p.id as p_id,
        si.name
    FROM supplier_items si
    JOIN suppliers s ON si.supplier_id = s.id
    JOIN products p ON p.name = si.name
    WHERE s.name = 'YOUR_SUPPLIER_NAME'
      AND si.product_id IS NULL
)
UPDATE supplier_items
SET product_id = matched.p_id
FROM matched
WHERE supplier_items.id = matched.si_id;
"
```

### Step 6: Verify in Frontend

Open http://localhost:5173 to see the products in the catalog.

## Cleanup Test Data

To remove all test data for a supplier:

```bash
# Replace YOUR_SUPPLIER_NAME with your supplier name
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "
-- Delete products linked to this supplier's items
DELETE FROM products WHERE id IN (
    SELECT DISTINCT product_id FROM supplier_items 
    WHERE supplier_id IN (SELECT id FROM suppliers WHERE name = 'YOUR_SUPPLIER_NAME')
    AND product_id IS NOT NULL
);

-- Delete supplier (cascades to supplier_items, price_history, parsing_logs)
DELETE FROM suppliers WHERE name = 'YOUR_SUPPLIER_NAME';
"
```

## Quick Reference Commands

### Check Database Status

```bash
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "
SELECT 
    (SELECT COUNT(*) FROM suppliers) as suppliers,
    (SELECT COUNT(*) FROM supplier_items) as supplier_items,
    (SELECT COUNT(*) FROM products) as products,
    (SELECT COUNT(*) FROM products WHERE status = 'active') as active_products;
"
```

### View Supplier Items

```bash
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "
SELECT supplier_sku, name, current_price, characteristics
FROM supplier_items 
WHERE supplier_id IN (SELECT id FROM suppliers WHERE name = 'YOUR_SUPPLIER_NAME')
LIMIT 10;
"
```

### Check Parsing Errors

```bash
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "
SELECT row_number, error_message, raw_data
FROM parsing_logs
WHERE supplier_id IN (SELECT id FROM suppliers WHERE name = 'YOUR_SUPPLIER_NAME')
ORDER BY created_at DESC
LIMIT 10;
"
```

### Test API Endpoint

```bash
curl -s "http://localhost:3000/api/v1/catalog/?limit=10" | python3 -m json.tool
```

## Column Mapping Configuration

For sheets with non-standard column names, you can specify custom mapping in the source_config:

```json
{
  "sheet_url": "https://docs.google.com/spreadsheets/d/...",
  "sheet_name": "Sheet1",
  "column_mapping": {
    "sku": "Item Code",
    "name": "Product Description", 
    "price": "Wholesale Price"
  },
  "characteristic_columns": ["Color", "Size", "Material"],
  "header_row": 1,
  "data_start_row": 2
}
```

## Troubleshooting

### Authentication Errors

```
gspread.exceptions.APIError: 403
```

**Solution:** Ensure the Google Sheet is shared with the service account email from `credentials/google-credentials.json`.

### Missing Price Errors

```
Row X: Required field 'price' is empty
```

**Solution:** These rows are logged but not imported. Check the `parsing_logs` table for details.

### Redis Connection Errors

```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Solution:** Ensure Redis is running: `docker-compose up -d redis`

### Products Not Showing in Catalog

Products only appear in the catalog when:
1. Status is `'active'`
2. They are properly linked to supplier items

Check product status:
```bash
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "
SELECT id, name, status FROM products WHERE status != 'active';
"
```

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Google Sheets  │────▶│  Python Worker  │────▶│   PostgreSQL    │
│   (Data Source) │     │   (Phase 1)     │     │   (Database)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │◀────│    Bun API      │◀────│    Products     │
│   (Phase 3)     │     │   (Phase 2)     │     │ (Catalog Table) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Data Flow:**
1. **Parser** reads Google Sheet → creates `supplier_items`
2. **Admin** creates `products` from `supplier_items`
3. **Catalog API** serves active `products` to frontend
4. **Frontend** displays products with price ranges from linked supplier items

