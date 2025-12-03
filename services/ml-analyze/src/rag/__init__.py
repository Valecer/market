"""
RAG Core
========

Vector embeddings, similarity search, and LLM matching.

Components:
    - VectorService: Embedding generation and similarity search
    - MergerAgent: LLM-based product matching
    - prompt_templates: LangChain prompt templates for matching
"""

from src.rag.vector_service import VectorService
from src.rag.merger_agent import MergerAgent, LLMMatchResponse
from src.rag.prompt_templates import (
    MATCH_PROMPT,
    BATCH_MATCH_PROMPT,
    format_candidates_text,
    format_item_for_prompt,
)

__all__ = [
    "VectorService",
    "MergerAgent",
    "LLMMatchResponse",
    "MATCH_PROMPT",
    "BATCH_MATCH_PROMPT",
    "format_candidates_text",
    "format_item_for_prompt",
]

