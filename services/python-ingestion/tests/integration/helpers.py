"""Helper functions for integration tests."""
from decimal import Decimal
from typing import List
from src.models.parsed_item import ParsedSupplierItem


def create_test_parsed_items(count: int, start_price: Decimal = Decimal("10.00")) -> List[ParsedSupplierItem]:
    """Create test parsed items for testing.
    
    Args:
        count: Number of items to create
        start_price: Starting price (increments by $0.50 for each item)
    
    Returns:
        List of ParsedSupplierItem instances
    """
    items = []
    for i in range(count):
        items.append(ParsedSupplierItem(
            supplier_sku=f"TEST-SKU-{i+1:03d}",
            name=f"Test Product {i+1}",
            price=start_price + Decimal(str(i * 0.50)),
            characteristics={
                "color": ["red", "blue", "green"][i % 3],
                "size": ["S", "M", "L", "XL"][i % 4],
            }
        ))
    return items


def create_test_parsed_items_with_same_price(count: int, price: Decimal = Decimal("10.00")) -> List[ParsedSupplierItem]:
    """Create test items with the same price.
    
    Args:
        count: Number of items to create
        price: Price for all items
    
    Returns:
        List of ParsedSupplierItem instances
    """
    items = []
    for i in range(count):
        items.append(ParsedSupplierItem(
            supplier_sku=f"TEST-SKU-{i+1:03d}",
            name=f"Test Product {i+1}",
            price=price,
            characteristics={}
        ))
    return items

