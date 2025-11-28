"""Parser modules for data source parsing."""
from src.parsers.base_parser import ParserInterface
from src.parsers.parser_registry import (
    register_parser,
    get_parser,
    create_parser_instance,
    list_registered_parsers,
)
from src.parsers.stub_parser import StubParser
from src.parsers.google_sheets_parser import GoogleSheetsParser

# Register parsers
register_parser("stub", StubParser)
register_parser("google_sheets", GoogleSheetsParser)

__all__ = [
    "ParserInterface",
    "register_parser",
    "get_parser",
    "create_parser_instance",
    "list_registered_parsers",
    "StubParser",
    "GoogleSheetsParser",
]

