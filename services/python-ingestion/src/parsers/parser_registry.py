"""Parser registry for dynamic parser registration and retrieval."""
from typing import Dict, Type, Optional
from src.parsers.base_parser import ParserInterface
from src.errors.exceptions import ParserError


# Global registry mapping parser type strings to parser classes
_parser_registry: Dict[str, Type[ParserInterface]] = {}


def register_parser(parser_type: str, parser_class: Type[ParserInterface]) -> None:
    """Register a parser class for a given parser type.
    
    Args:
        parser_type: Unique identifier for the parser (e.g., "google_sheets")
        parser_class: Parser class that inherits from ParserInterface
    
    Raises:
        ValueError: If parser_type is already registered
        TypeError: If parser_class does not inherit from ParserInterface
    """
    if not issubclass(parser_class, ParserInterface):
        raise TypeError(
            f"Parser class {parser_class.__name__} must inherit from ParserInterface"
        )
    
    if parser_type in _parser_registry:
        raise ValueError(
            f"Parser type '{parser_type}' is already registered. "
            f"Existing: {_parser_registry[parser_type].__name__}"
        )
    
    _parser_registry[parser_type] = parser_class


def get_parser(parser_type: str) -> Optional[Type[ParserInterface]]:
    """Get parser class for a given parser type.
    
    Args:
        parser_type: Parser type identifier (e.g., "google_sheets")
    
    Returns:
        Parser class if found, None otherwise
    """
    return _parser_registry.get(parser_type)


def create_parser_instance(parser_type: str, **kwargs) -> ParserInterface:
    """Create an instance of a parser for a given parser type.
    
    Args:
        parser_type: Parser type identifier
        **kwargs: Arguments to pass to parser constructor
    
    Returns:
        Parser instance
    
    Raises:
        ParserError: If parser type is not registered
    """
    parser_class = get_parser(parser_type)
    if parser_class is None:
        available = ", ".join(_parser_registry.keys()) if _parser_registry else "none"
        raise ParserError(
            f"Parser type '{parser_type}' is not registered. "
            f"Available parsers: {available}"
        )
    
    try:
        return parser_class(**kwargs)
    except Exception as e:
        raise ParserError(
            f"Failed to create parser instance for '{parser_type}': {e}"
        ) from e


def list_registered_parsers() -> list[str]:
    """List all registered parser types.
    
    Returns:
        List of registered parser type strings
    """
    return list(_parser_registry.keys())

