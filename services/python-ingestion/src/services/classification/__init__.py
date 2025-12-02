"""Product classification service.

This module provides intelligent product categorization using:
- Keyword-based rules
- Brand detection
- Fuzzy matching fallbacks

Key Components:
    - CategoryClassifier: Rule-based classifier
    - BrandDetector: Brand extraction from product names
"""
from src.services.classification.classifier import (
    CategoryClassifier,
    ClassificationResult,
    CategoryRule,
)

__all__ = [
    "CategoryClassifier",
    "ClassificationResult",
    "CategoryRule",
]

