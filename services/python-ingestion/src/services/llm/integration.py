"""Integration layer for LLM services with parsers and matching pipeline.

This module provides easy-to-use functions that combine LLM services
with the existing parser and matching infrastructure.

Example:
    from src.services.llm.integration import enhance_parser_with_llm
    
    # Enhance existing parser result
    enhanced_items = await enhance_parser_with_llm(parsed_items, supplier_id)
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import structlog

from ...config import llm_settings, LLMBackendType
from ...models.parsed_item import ParsedItem
from .client import LLMClient, LLMConfig, OllamaClient, MockLLMClient, LLMBackend
from .header_analyzer import LLMHeaderAnalyzer, HeaderAnalysisResult
from .product_classifier import LLMProductClassifier, ClassificationResult, ExtractedFeatures

logger = structlog.get_logger(__name__)


@dataclass
class EnhancedParseResult:
    """Result of LLM-enhanced parsing."""
    items: List[ParsedItem]
    classifications: Dict[int, ClassificationResult]  # item_index -> classification
    features: Dict[int, ExtractedFeatures]  # item_index -> features
    groupings: Dict[str, List[int]]  # group_key -> item_indices
    llm_used: bool
    stats: Dict[str, Any]


def get_configured_llm_client() -> LLMClient:
    """Get LLM client configured from settings.
    
    Returns:
        Configured LLMClient instance
    """
    if not llm_settings.enabled:
        logger.info("llm_disabled_using_mock")
        return MockLLMClient()
    
    # Map settings backend to LLMBackend enum
    backend_map = {
        LLMBackendType.OLLAMA: LLMBackend.OLLAMA,
        LLMBackendType.OPENAI: LLMBackend.OPENAI,
        LLMBackendType.MOCK: LLMBackend.MOCK,
    }
    
    config = LLMConfig(
        backend=backend_map.get(llm_settings.backend, LLMBackend.OLLAMA),
        model=llm_settings.model,
        base_url=llm_settings.ollama_url,
        api_key=llm_settings.openai_api_key,
        timeout=llm_settings.timeout,
        max_retries=llm_settings.max_retries,
        temperature=llm_settings.temperature,
        max_tokens=llm_settings.max_tokens,
    )
    
    if config.backend == LLMBackend.MOCK:
        return MockLLMClient(config)
    
    return OllamaClient(config)


async def analyze_sheet_headers(
    rows: List[List[str]],
    sheet_name: str = "",
    hint_header_row: Optional[int] = None,
) -> HeaderAnalysisResult:
    """Analyze spreadsheet headers using LLM.
    
    Falls back to rule-based analysis if LLM is not available.
    
    Args:
        rows: Spreadsheet data as list of rows
        sheet_name: Optional sheet name for context
        hint_header_row: Optional hint for header row position
        
    Returns:
        HeaderAnalysisResult with detected structure
    """
    if not llm_settings.enabled or not llm_settings.use_for_headers:
        logger.debug("llm_headers_disabled_using_rules")
        analyzer = LLMHeaderAnalyzer(client=MockLLMClient())
        return await analyzer._fallback_analysis(rows)
    
    client = get_configured_llm_client()
    analyzer = LLMHeaderAnalyzer(client=client)
    
    return await analyzer.analyze_headers(
        rows=rows,
        sheet_name=sheet_name,
        hint_header_row=hint_header_row,
    )


async def classify_product(
    product_name: str,
    description: Optional[str] = None,
    supplier_category: Optional[str] = None,
) -> ClassificationResult:
    """Classify a single product using LLM.
    
    Args:
        product_name: Product name/title
        description: Optional product description
        supplier_category: Optional category from supplier
        
    Returns:
        ClassificationResult with category and confidence
    """
    if not llm_settings.enabled or not llm_settings.use_for_classification:
        classifier = LLMProductClassifier(client=MockLLMClient())
        return await classifier._fallback_classification(product_name, supplier_category)
    
    client = get_configured_llm_client()
    classifier = LLMProductClassifier(client=client)
    
    return await classifier.classify_product(
        product_name=product_name,
        description=description,
        supplier_category=supplier_category,
    )


async def batch_classify_products(
    products: List[str],
    batch_size: int = 10,
) -> List[ClassificationResult]:
    """Classify multiple products efficiently.
    
    Args:
        products: List of product names
        batch_size: Products per batch
        
    Returns:
        List of ClassificationResult for each product
    """
    if not llm_settings.enabled or not llm_settings.use_for_classification:
        classifier = LLMProductClassifier(client=MockLLMClient())
        results = []
        for product in products:
            result = await classifier._fallback_classification(product, None)
            results.append(result)
        return results
    
    client = get_configured_llm_client()
    classifier = LLMProductClassifier(client=client)
    
    return await classifier.batch_classify(products, batch_size)


async def compare_products(
    product1: str,
    product2: str,
) -> Tuple[bool, float, str]:
    """Compare two products for similarity.
    
    Args:
        product1: First product name
        product2: Second product name
        
    Returns:
        (are_similar, confidence, reasoning)
    """
    if not llm_settings.enabled or not llm_settings.use_for_matching:
        from rapidfuzz import fuzz
        score = fuzz.token_sort_ratio(product1.lower(), product2.lower()) / 100.0
        return score >= 0.7, 0.6, f"Rule-based similarity: {score:.2f}"
    
    client = get_configured_llm_client()
    classifier = LLMProductClassifier(client=client)
    
    result = await classifier.compare_products(product1, product2)
    return result.are_similar, result.confidence, result.reasoning or ""


async def enhance_parsed_items(
    items: List[ParsedItem],
    supplier_category: Optional[str] = None,
) -> EnhancedParseResult:
    """Enhance parsed items with LLM classification and features.
    
    This is the main integration point for enriching parsed data
    with ML-based classification and feature extraction.
    
    Args:
        items: List of parsed items from parser
        supplier_category: Optional category context from supplier
        
    Returns:
        EnhancedParseResult with classifications and features
    """
    log = logger.bind(items_count=len(items))
    
    if not items:
        return EnhancedParseResult(
            items=[],
            classifications={},
            features={},
            groupings={},
            llm_used=False,
            stats={"total": 0},
        )
    
    llm_available = llm_settings.enabled and llm_settings.use_for_classification
    
    if not llm_available:
        log.debug("llm_not_enabled_returning_basic_result")
        return EnhancedParseResult(
            items=items,
            classifications={},
            features={},
            groupings={},
            llm_used=False,
            stats={"total": len(items), "classified": 0},
        )
    
    client = get_configured_llm_client()
    classifier = LLMProductClassifier(client=client)
    
    # Check if LLM is actually available
    if not await client.is_available():
        log.warning("llm_not_available_returning_basic_result")
        return EnhancedParseResult(
            items=items,
            classifications={},
            features={},
            groupings={},
            llm_used=False,
            stats={"total": len(items), "classified": 0, "reason": "LLM not available"},
        )
    
    classifications: Dict[int, ClassificationResult] = {}
    features: Dict[int, ExtractedFeatures] = {}
    
    # Batch classify products
    product_names = [item.name for item in items]
    
    try:
        results = await classifier.batch_classify(product_names, batch_size=10)
        
        for idx, result in enumerate(results):
            classifications[idx] = result
        
        # Extract features for high-confidence classifications
        for idx, item in enumerate(items):
            if idx in classifications and classifications[idx].confidence >= 0.5:
                try:
                    item_features = await classifier.extract_features(item.name)
                    features[idx] = item_features
                except Exception:
                    pass
        
        # Suggest groupings
        groupings: Dict[str, List[int]] = {}
        try:
            group_results = await classifier.suggest_groupings(product_names[:50])
            for group in group_results:
                groupings[group.group_key] = [
                    product_names.index(p) 
                    for p in group.products 
                    if p in product_names
                ]
        except Exception as e:
            log.warning("grouping_failed", error=str(e))
        
        log.info(
            "items_enhanced",
            classified=len(classifications),
            features_extracted=len(features),
            groups_found=len(groupings),
        )
        
        return EnhancedParseResult(
            items=items,
            classifications=classifications,
            features=features,
            groupings=groupings,
            llm_used=True,
            stats={
                "total": len(items),
                "classified": len(classifications),
                "features_extracted": len(features),
                "groups": len(groupings),
            },
        )
        
    except Exception as e:
        log.error("enhancement_failed", error=str(e))
        return EnhancedParseResult(
            items=items,
            classifications={},
            features={},
            groupings={},
            llm_used=False,
            stats={"total": len(items), "error": str(e)},
        )


async def find_similar_products(
    product_name: str,
    candidates: List[str],
    threshold: float = 0.7,
) -> List[Tuple[str, float]]:
    """Find similar products from a list of candidates.
    
    Args:
        product_name: Product to find matches for
        candidates: List of potential matches
        threshold: Minimum similarity threshold
        
    Returns:
        List of (candidate_name, similarity_score) tuples
    """
    if not candidates:
        return []
    
    if not llm_settings.enabled or not llm_settings.use_for_matching:
        # Use RapidFuzz for rule-based matching
        from rapidfuzz import fuzz, process
        
        matches = process.extract(
            product_name.lower(),
            [c.lower() for c in candidates],
            scorer=fuzz.token_sort_ratio,
            limit=10,
        )
        
        return [
            (candidates[idx], score / 100.0)
            for _, score, idx in matches
            if score / 100.0 >= threshold
        ]
    
    # Use LLM for semantic matching
    client = get_configured_llm_client()
    classifier = LLMProductClassifier(client=client)
    
    results = []
    for candidate in candidates[:20]:  # Limit to avoid too many API calls
        try:
            similarity = await classifier.compare_products(product_name, candidate)
            if similarity.similarity_score >= threshold:
                results.append((candidate, similarity.similarity_score))
        except Exception:
            continue
    
    return sorted(results, key=lambda x: x[1], reverse=True)


# Convenience functions for common use cases

async def auto_categorize_supplier_items(
    items: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Automatically categorize supplier items into groups.
    
    Args:
        items: List of item dictionaries with 'name' key
        
    Returns:
        Dict mapping category to list of items in that category
    """
    if not items:
        return {}
    
    names = [item.get("name", "") for item in items]
    classifications = await batch_classify_products(names)
    
    categorized: Dict[str, List[Dict[str, Any]]] = {}
    
    for item, classification in zip(items, classifications):
        category = classification.category
        if category not in categorized:
            categorized[category] = []
        
        # Add classification info to item
        item["_category"] = category
        item["_category_confidence"] = classification.confidence
        categorized[category].append(item)
    
    return categorized


async def is_llm_available() -> bool:
    """Check if LLM service is available and configured.
    
    Returns:
        True if LLM can be used for operations
    """
    if not llm_settings.enabled:
        return False
    
    client = get_configured_llm_client()
    return await client.is_available()

