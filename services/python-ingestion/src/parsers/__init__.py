"""Parser modules for data source parsing."""
from src.parsers.base_parser import ParserInterface
from src.parsers.parser_registry import (
    register_parser,
    get_parser,
    create_parser_instance,
    list_registered_parsers,
)
from src.parsers.stub_parser import StubParser

# Register stub parser for testing
register_parser("stub", StubParser)

__all__ = [
    "ParserInterface",
    "register_parser",
    "get_parser",
    "create_parser_instance",
    "list_registered_parsers",
    "StubParser",
]

