"""Feature extraction services for enriching supplier item data.

This module provides strategies for extracting technical specifications
from supplier item text using pattern matching.

Key Components:
    - FeatureExtractor: Abstract base class for extraction algorithms
    - ElectronicsExtractor: Extracts voltage, power specifications
    - DimensionsExtractor: Extracts weight, dimensions
    - EXTRACTOR_REGISTRY: Dictionary of available extractors
    - create_extractor: Factory function for extractor creation
    - extract_all_features: Run multiple extractors and merge results
"""
from src.services.extraction.extractors import (
    FeatureExtractor,
    ElectronicsExtractor,
    DimensionsExtractor,
    EXTRACTOR_REGISTRY,
    create_extractor,
    extract_all_features,
)

__all__: list[str] = [
    "FeatureExtractor",
    "ElectronicsExtractor",
    "DimensionsExtractor",
    "EXTRACTOR_REGISTRY",
    "create_extractor",
    "extract_all_features",
]

