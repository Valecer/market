"""
Smart Parser Module for Semantic ETL Pipeline
==============================================

Phase 9: LLM-based product extraction from supplier files.

Components:
- MarkdownConverter: Excel/CSV → Markdown table conversion
- LangChainExtractor: LLM-based product extraction with sliding window
- SmartParserService: Orchestration layer

Usage:
    from src.services.smart_parser import SmartParserService
    
    async with async_session() as session:
        service = SmartParserService(session)
        result = await service.parse_file(file_path, supplier_id, job_id)
"""

from src.services.smart_parser.markdown_converter import MarkdownConverter
from src.services.smart_parser.langchain_extractor import LangChainExtractor
from src.services.smart_parser.service import SmartParserService

__all__ = [
    "MarkdownConverter",
    "LangChainExtractor",
    "SmartParserService",
]

