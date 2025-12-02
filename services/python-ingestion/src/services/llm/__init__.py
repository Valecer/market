"""LLM service module for ML-based matching and classification.

Supports:
- Ollama (recommended for local deployment)
- OpenAI API (optional)
- Fallback to rule-based matching

Usage:
    from src.services.llm import LLMClient, get_llm_client
    
    client = get_llm_client()
    response = await client.complete("Analyze this product...")
"""

from .client import LLMClient, OllamaClient, get_llm_client
from .header_analyzer import LLMHeaderAnalyzer
from .product_classifier import LLMProductClassifier

__all__ = [
    "LLMClient",
    "OllamaClient", 
    "get_llm_client",
    "LLMHeaderAnalyzer",
    "LLMProductClassifier",
]

