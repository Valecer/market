"""Stub parser for testing parser registration mechanism."""
from typing import List, Dict, Any
from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from src.errors.exceptions import ValidationError


class StubParser(ParserInterface):
    """Stub parser implementation for testing.
    
    This parser returns a fixed set of test data and is used to verify
    that the parser registration and invocation mechanism works correctly.
    """
    
    def __init__(self):
        """Initialize stub parser."""
        pass
    
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Return a fixed set of test items.
        
        Args:
            config: Configuration dictionary (ignored for stub)
        
        Returns:
            List of 3 test ParsedSupplierItem objects
        """
        return [
            ParsedSupplierItem(
                supplier_sku="STUB-001",
                name="Test Product 1",
                price=10.99,
                characteristics={"color": "red", "size": "M"}
            ),
            ParsedSupplierItem(
                supplier_sku="STUB-002",
                name="Test Product 2",
                price=25.50,
                characteristics={"color": "blue", "size": "L"}
            ),
            ParsedSupplierItem(
                supplier_sku="STUB-003",
                name="Test Product 3",
                price=5.00,
                characteristics={"color": "green"}
            ),
        ]
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate stub parser configuration.
        
        Args:
            config: Configuration dictionary
        
        Returns:
            True if config is valid (always True for stub)
        
        Raises:
            ValidationError: If config is missing required fields
        """
        # Stub parser accepts any config, but we can add validation if needed
        if not isinstance(config, dict):
            raise ValidationError("Config must be a dictionary")
        return True
    
    def get_parser_name(self) -> str:
        """Return parser identifier.
        
        Returns:
            "stub" as the parser type identifier
        """
        return "stub"

