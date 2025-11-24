"""Abstract parser interface for pluggable data sources."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.models.parsed_item import ParsedSupplierItem


class ParserInterface(ABC):
    """Abstract base class for all data source parsers.
    
    This interface enables pluggable parser architecture where new data sources
    (Google Sheets, CSV, Excel) can be added without modifying core service code.
    
    Implementations must provide:
    - parse(): Extract and validate data from source
    - validate_config(): Verify parser-specific configuration
    - get_parser_name(): Return unique parser identifier
    """
    
    @abstractmethod
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Parse data from source and return validated items.
        
        Args:
            config: Parser-specific configuration dictionary containing
                   source location, authentication, column mappings, etc.
        
        Returns:
            List of validated ParsedSupplierItem objects
        
        Raises:
            ParserError: If parsing fails due to source access issues
            ValidationError: If data validation fails (should be logged, not raised)
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate parser-specific configuration before parsing.
        
        Args:
            config: Configuration dictionary to validate
        
        Returns:
            True if configuration is valid, False otherwise
        
        Raises:
            ValidationError: If configuration is invalid with detailed message
        """
        pass
    
    @abstractmethod
    def get_parser_name(self) -> str:
        """Return unique identifier for this parser type.
        
        Returns:
            Parser identifier string (e.g., "google_sheets", "csv", "excel")
        """
        pass

