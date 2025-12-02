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
    - ProductNameParser: Parses raw names into category/brand/model/characteristics
    - parse_product_name: Convenience function for name parsing
"""
from src.services.extraction.extractors import (
    FeatureExtractor,
    ElectronicsExtractor,
    DimensionsExtractor,
    EXTRACTOR_REGISTRY,
    create_extractor,
    extract_all_features,
)
from src.services.extraction.name_parser import (
    ProductNameParser,
    ParsedProductName,
    parse_product_name,
)

__all__: list[str] = [
    "FeatureExtractor",
    "ElectronicsExtractor",
    "DimensionsExtractor",
    "EXTRACTOR_REGISTRY",
    "create_extractor",
    "extract_all_features",
    "ProductNameParser",
    "ParsedProductName",
    "parse_product_name",
]

