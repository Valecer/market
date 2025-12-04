-- Seed Data: Categories for Review Workflow Testing
-- Phase 9: Semantic ETL - Category Governance
-- 
-- This file creates sample categories with needs_review=true
-- for testing the category review workflow.
--
-- Usage:
--   docker exec -i marketbel-postgres psql -U marketbel_user -d marketbel < specs/009-semantic-etl/test_data/test_categories_review.sql

-- First, ensure we have a test supplier
INSERT INTO suppliers (id, name, source_type, metadata)
SELECT 
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid,
    'Test Supplier for Categories',
    'excel',
    '{"test": true}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM suppliers WHERE id = 'a1b2c3d4-0000-4000-8000-000000000001'::uuid
);

-- Create parent categories (approved, no review needed)
INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
VALUES 
    ('Electronics', NULL, false, true, NULL),
    ('Home & Garden', NULL, false, true, NULL),
    ('Sports & Outdoors', NULL, false, true, NULL)
ON CONFLICT (name, parent_id) DO NOTHING;

-- Create categories needing review (from semantic ETL)
INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Laptops & Notebooks',
    (SELECT id FROM categories WHERE name = 'Electronics' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Laptops & Notebooks'
);

INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Gaming Accessories',
    (SELECT id FROM categories WHERE name = 'Electronics' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Gaming Accessories'
);

INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Smart Home Devices',
    (SELECT id FROM categories WHERE name = 'Electronics' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Smart Home Devices'
);

INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Garden Tools',
    (SELECT id FROM categories WHERE name = 'Home & Garden' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Garden Tools'
);

INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Outdoor Furniture',
    (SELECT id FROM categories WHERE name = 'Home & Garden' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Outdoor Furniture'
);

INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Camping Equipment',
    (SELECT id FROM categories WHERE name = 'Sports & Outdoors' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Camping Equipment'
);

INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Fitness Trackers',
    (SELECT id FROM categories WHERE name = 'Sports & Outdoors' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Fitness Trackers'
);

-- Create some potential duplicates for merge testing
INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Notebook Computers',  -- Similar to "Laptops & Notebooks"
    (SELECT id FROM categories WHERE name = 'Electronics' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Notebook Computers'
);

INSERT INTO categories (name, parent_id, needs_review, is_active, supplier_id)
SELECT
    'Gardening Tools',  -- Similar to "Garden Tools"
    (SELECT id FROM categories WHERE name = 'Home & Garden' LIMIT 1),
    true,
    true,
    'a1b2c3d4-0000-4000-8000-000000000001'::uuid
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Gardening Tools'
);

-- Verify the seed data
SELECT 
    c.name,
    c.needs_review,
    c.is_active,
    pc.name as parent_name,
    s.name as supplier_name
FROM categories c
LEFT JOIN categories pc ON c.parent_id = pc.id
LEFT JOIN suppliers s ON c.supplier_id = s.id
WHERE c.needs_review = true
ORDER BY pc.name NULLS FIRST, c.name;

