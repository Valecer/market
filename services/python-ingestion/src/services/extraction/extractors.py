"""Feature extraction strategies using regex pattern matching.

This module implements FR-2: Characteristics Extractor ("The Enricher").
It extracts technical specifications from supplier item text using 
regex patterns for various product categories.

Key Components:
    - FeatureExtractor: Abstract base class for extraction algorithms
    - ElectronicsExtractor: Extracts voltage, power, storage, memory
    - DimensionsExtractor: Extracts weight, dimensions (L x W x H)
    - EXTRACTOR_REGISTRY: Dictionary of available extractors by name

SOLID Compliance:
    - Open/Closed: New extractors can be added without modifying existing code
    - Single Responsibility: Each extractor handles one category of features
    - Liskov Substitution: All extractors implement the same interface

Pattern Matching Strategy (KISS):
    - Use regex patterns hardcoded in Python classes (no database complexity)
    - Patterns are case-insensitive
    - Multiple patterns per feature type for flexibility
    - Invalid/ambiguous values are filtered by Pydantic validators
"""
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type
import structlog

from src.models.extraction import ExtractedFeatures, DimensionsCm

logger = structlog.get_logger(__name__)


class FeatureExtractor(ABC):
    """Abstract base class for feature extraction strategies.
    
    This follows the Strategy pattern (SOLID-O: Open/Closed Principle)
    allowing new extractors to be added without modifying existing code.
    
    All implementations must honor the contract:
        - extract() returns ExtractedFeatures with found values
        - get_extractor_name() returns unique extractor identifier
        - Patterns are case-insensitive
        - Invalid values are filtered (handled by Pydantic validators)
    """
    
    @abstractmethod
    def extract(self, text: str) -> ExtractedFeatures:
        """Extract features from text.
        
        Args:
            text: Input text to extract features from (e.g., product name)
            
        Returns:
            ExtractedFeatures with any found values
        """
        pass
    
    @abstractmethod
    def get_extractor_name(self) -> str:
        """Get the name of this extractor.
        
        Returns:
            Unique identifier for this extractor (e.g., "electronics")
        """
        pass


class ElectronicsExtractor(FeatureExtractor):
    """Extract electrical and electronics specifications.
    
    Extracts:
        - Voltage (V): "220V", "110 V", "220 volt", "220-240V"
        - Power (W): "750W", "1.5kW", "750 watt", "750Вт"
        - Storage (GB/TB): "128GB", "1TB", "512 GB SSD"
        - Memory (GB): "8GB RAM", "16 GB memory", "8GB DDR4"
    
    Pattern Strategy:
        - Match common formats found in product names
        - Handle both metric and imperial notations
        - Support range formats (e.g., "220-240V" takes first value)
    """
    
    # Voltage patterns (case-insensitive)
    VOLTAGE_PATTERNS = [
        # "220V", "220 V", "220v"
        r'(\d{2,4})\s*[vVвВ](?:\s|$|[^a-zA-Z])',
        # "220 volt", "220 volts", "220вольт"
        r'(\d{2,4})\s*(?:volt|volts|вольт)',
        # "220-240V" (range - take first)
        r'(\d{2,4})\s*[-–]\s*\d{2,4}\s*[vVвВ]',
        # "AC 220V", "AC220"
        r'AC\s*(\d{2,4})\s*[vVвВ]?',
    ]
    
    # Power patterns (case-insensitive)
    POWER_PATTERNS = [
        # "750W", "750 W", "750w", "750Вт"
        r'(\d{1,5})\s*[wWвВ](?:att|t|атт)?(?:\s|$|[^a-zA-Z])',
        # "1.5kW", "1.5 kW", "1500W" equivalent patterns
        r'(\d+(?:[.,]\d+)?)\s*[kкКK]\s*[wWвВ](?:att|t|атт)?',
        # "HP 1.5" (horsepower - convert to watts approx 746W/HP)
        r'(\d+(?:[.,]\d+)?)\s*HP',
    ]
    
    # Storage patterns
    STORAGE_PATTERNS = [
        # "128GB", "128 GB"
        r'(\d{1,5})\s*[gGгГ][bBбБ](?:\s|$|[^a-zA-Z])',
        # "1TB", "2 TB"
        r'(\d{1,2})\s*[tTтТ][bBбБ](?:\s|$|[^a-zA-Z])',
        # "512GB SSD", "256 GB HDD"
        r'(\d{1,4})\s*[gGгГ][bBбБ]\s*(?:SSD|HDD|NVMe)',
        # SSD/HDD with space: "SSD 512GB"
        r'(?:SSD|HDD|NVMe)\s*(\d{1,4})\s*[gGгГ][bBбБ]',
    ]
    
    # Memory patterns (RAM)
    MEMORY_PATTERNS = [
        # "8GB RAM", "16 GB RAM"
        r'(\d{1,3})\s*[gGгГ][bBбБ]\s*(?:RAM|DDR|memory|ОЗУ)',
        # "RAM 8GB", "DDR4 16GB"
        r'(?:RAM|DDR\d?|memory|ОЗУ)\s*(\d{1,3})\s*[gGгГ][bBбБ]',
    ]
    
    def __init__(self):
        """Initialize the electronics extractor with compiled patterns."""
        self._voltage_re = [re.compile(p, re.IGNORECASE) for p in self.VOLTAGE_PATTERNS]
        self._power_re = [re.compile(p, re.IGNORECASE) for p in self.POWER_PATTERNS]
        self._storage_re = [re.compile(p, re.IGNORECASE) for p in self.STORAGE_PATTERNS]
        self._memory_re = [re.compile(p, re.IGNORECASE) for p in self.MEMORY_PATTERNS]
        self._log = logger.bind(extractor="ElectronicsExtractor")
    
    def get_extractor_name(self) -> str:
        """Get the name of this extractor."""
        return "electronics"
    
    def extract(self, text: str) -> ExtractedFeatures:
        """Extract electrical specifications from text.
        
        Args:
            text: Product name or description text
            
        Returns:
            ExtractedFeatures with voltage, power, storage, memory
        """
        voltage = self._extract_voltage(text)
        power_watts = self._extract_power(text)
        storage_gb = self._extract_storage(text)
        memory_gb = self._extract_memory(text)
        
        result = ExtractedFeatures(
            voltage=voltage,
            power_watts=power_watts,
            storage_gb=storage_gb,
            memory_gb=memory_gb,
        )
        
        if result.has_any_features():
            self._log.debug(
                "electronics_extracted",
                text=text[:100],
                voltage=voltage,
                power_watts=power_watts,
                storage_gb=storage_gb,
                memory_gb=memory_gb,
            )
        
        return result
    
    def _extract_voltage(self, text: str) -> Optional[int]:
        """Extract voltage value from text."""
        for pattern in self._voltage_re:
            match = pattern.search(text)
            if match:
                try:
                    value = int(match.group(1))
                    # Validate reasonable voltage range
                    if 1 <= value <= 10000:
                        return value
                except (ValueError, IndexError):
                    continue
        return None
    
    def _extract_power(self, text: str) -> Optional[int]:
        """Extract power value from text (in watts)."""
        for i, pattern in enumerate(self._power_re):
            match = pattern.search(text)
            if match:
                try:
                    raw_value = match.group(1).replace(',', '.')
                    value = float(raw_value)
                    
                    # Check if this is a kW pattern (index 1) - multiply by 1000
                    if i == 1:  # kW pattern
                        value = int(value * 1000)
                    # Check if HP pattern (index 2) - convert to watts
                    elif i == 2:  # HP pattern
                        value = int(value * 746)  # 1 HP ≈ 746 W
                    else:
                        value = int(value)
                    
                    # Validate reasonable power range
                    if 1 <= value <= 100000:
                        return value
                except (ValueError, IndexError):
                    continue
        return None
    
    def _extract_storage(self, text: str) -> Optional[int]:
        """Extract storage capacity from text (in GB)."""
        for i, pattern in enumerate(self._storage_re):
            match = pattern.search(text)
            if match:
                try:
                    value = int(match.group(1))
                    
                    # TB pattern (index 1) - multiply by 1000
                    if i == 1:
                        value = value * 1000
                    
                    # Validate reasonable storage range
                    if 1 <= value <= 100000:
                        return value
                except (ValueError, IndexError):
                    continue
        return None
    
    def _extract_memory(self, text: str) -> Optional[int]:
        """Extract memory/RAM from text (in GB)."""
        for pattern in self._memory_re:
            match = pattern.search(text)
            if match:
                try:
                    value = int(match.group(1))
                    # Validate reasonable RAM range (1-1000 GB)
                    if 1 <= value <= 1000:
                        return value
                except (ValueError, IndexError):
                    continue
        return None


class DimensionsExtractor(FeatureExtractor):
    """Extract physical dimensions and weight specifications.
    
    Extracts:
        - Weight (kg): "2.5kg", "2.5 kg", "2500g", "5.5 lbs"
        - Dimensions (cm): "30x20x10cm", "30 x 20 x 10 cm", "L30 W20 H10"
    
    Pattern Strategy:
        - Handle metric (kg, g, cm, mm) and imperial (lbs, in)
        - Support various delimiter formats (x, ×, by, *)
        - Convert imperial to metric where possible
    """
    
    # Weight patterns
    WEIGHT_PATTERNS = [
        # "2.5kg", "2.5 kg", "2,5 kg"
        r'(\d+(?:[.,]\d+)?)\s*[kкКK][gгГG](?:\s|$|[^a-zA-Z])',
        # "2500g", "2500 g"
        r'(\d+(?:[.,]\d+)?)\s*[gгГG](?:\s|$|[^a-zA-Z])',
        # "5.5 lbs", "5.5lb"
        r'(\d+(?:[.,]\d+)?)\s*(?:lbs?|pounds?)',
        # "weight: 2.5kg"
        r'(?:weight|вес|масса)[:\s]+(\d+(?:[.,]\d+)?)\s*[kкКK]?[gгГG]?',
    ]
    
    # Dimension patterns (L x W x H format)
    DIMENSION_PATTERNS = [
        # "30x20x10cm", "30 x 20 x 10 cm"
        r'(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*(?:cm|см)',
        # "30x20x10 mm"
        r'(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*(?:mm|мм)',
        # "30x20x10" (without unit, assume cm)
        r'(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)(?:\s|$)',
        # "L30 W20 H10 cm"
        r'[lLдД][:.\s]*(\d+(?:[.,]\d+)?)\s*[wWшШ][:.\s]*(\d+(?:[.,]\d+)?)\s*[hHвВ][:.\s]*(\d+(?:[.,]\d+)?)',
        # "12x8x4 in" (inches)
        r'(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*(?:in|inch|дюйм)',
    ]
    
    def __init__(self):
        """Initialize the dimensions extractor with compiled patterns."""
        self._weight_re = [re.compile(p, re.IGNORECASE) for p in self.WEIGHT_PATTERNS]
        self._dimension_re = [re.compile(p, re.IGNORECASE) for p in self.DIMENSION_PATTERNS]
        self._log = logger.bind(extractor="DimensionsExtractor")
    
    def get_extractor_name(self) -> str:
        """Get the name of this extractor."""
        return "dimensions"
    
    def extract(self, text: str) -> ExtractedFeatures:
        """Extract physical dimensions from text.
        
        Args:
            text: Product name or description text
            
        Returns:
            ExtractedFeatures with weight_kg, dimensions_cm
        """
        weight_kg = self._extract_weight(text)
        dimensions_cm = self._extract_dimensions(text)
        
        result = ExtractedFeatures(
            weight_kg=weight_kg,
            dimensions_cm=dimensions_cm,
        )
        
        if result.has_any_features():
            self._log.debug(
                "dimensions_extracted",
                text=text[:100],
                weight_kg=weight_kg,
                dimensions_cm=dimensions_cm.model_dump() if dimensions_cm else None,
            )
        
        return result
    
    def _extract_weight(self, text: str) -> Optional[float]:
        """Extract weight value from text (in kg)."""
        for i, pattern in enumerate(self._weight_re):
            match = pattern.search(text)
            if match:
                try:
                    raw_value = match.group(1).replace(',', '.')
                    value = float(raw_value)
                    
                    # Convert grams to kg (index 1)
                    if i == 1:
                        value = value / 1000
                    # Convert lbs to kg (index 2)
                    elif i == 2:
                        value = value * 0.453592  # 1 lb ≈ 0.453592 kg
                    
                    # Validate reasonable weight range
                    if 0.001 <= value <= 10000:
                        return round(value, 3)
                except (ValueError, IndexError):
                    continue
        return None
    
    def _extract_dimensions(self, text: str) -> Optional[DimensionsCm]:
        """Extract dimensions from text (L x W x H in cm)."""
        for i, pattern in enumerate(self._dimension_re):
            match = pattern.search(text)
            if match:
                try:
                    l = float(match.group(1).replace(',', '.'))
                    w = float(match.group(2).replace(',', '.'))
                    h = float(match.group(3).replace(',', '.'))
                    
                    # Convert mm to cm (index 1)
                    if i == 1:
                        l, w, h = l / 10, w / 10, h / 10
                    # Convert inches to cm (index 4)
                    elif i == 4:
                        l, w, h = l * 2.54, w * 2.54, h * 2.54
                    
                    # Validate all dimensions are positive and reasonable
                    if all(0.1 <= d <= 100000 for d in [l, w, h]):
                        return DimensionsCm(
                            length=round(l, 2),
                            width=round(w, 2),
                            height=round(h, 2),
                        )
                except (ValueError, IndexError):
                    continue
        return None


# Registry of available extractors by name
EXTRACTOR_REGISTRY: Dict[str, Type[FeatureExtractor]] = {
    "electronics": ElectronicsExtractor,
    "dimensions": DimensionsExtractor,
}


def create_extractor(name: str) -> FeatureExtractor:
    """Factory function to create an extractor by name.
    
    Args:
        name: Extractor name from EXTRACTOR_REGISTRY
        
    Returns:
        FeatureExtractor instance
        
    Raises:
        ValueError: If unknown extractor name
    """
    if name not in EXTRACTOR_REGISTRY:
        raise ValueError(
            f"Unknown extractor: {name}. "
            f"Available: {list(EXTRACTOR_REGISTRY.keys())}"
        )
    
    return EXTRACTOR_REGISTRY[name]()


def extract_all_features(
    text: str,
    extractors: Optional[List[str]] = None,
) -> ExtractedFeatures:
    """Run multiple extractors and merge results.
    
    Args:
        text: Input text to extract features from
        extractors: List of extractor names to apply (default: all)
        
    Returns:
        ExtractedFeatures with merged results from all extractors
    """
    if extractors is None:
        extractors = list(EXTRACTOR_REGISTRY.keys())
    
    log = logger.bind(text_preview=text[:50], extractors=extractors)
    log.debug("extracting_all_features")
    
    # Start with empty result
    merged = ExtractedFeatures()
    extractors_applied = []
    
    for name in extractors:
        try:
            extractor = create_extractor(name)
            result = extractor.extract(text)
            
            # Merge results (first non-None value wins)
            if result.voltage is not None and merged.voltage is None:
                merged.voltage = result.voltage
            if result.power_watts is not None and merged.power_watts is None:
                merged.power_watts = result.power_watts
            if result.weight_kg is not None and merged.weight_kg is None:
                merged.weight_kg = result.weight_kg
            if result.dimensions_cm is not None and merged.dimensions_cm is None:
                merged.dimensions_cm = result.dimensions_cm
            if result.storage_gb is not None and merged.storage_gb is None:
                merged.storage_gb = result.storage_gb
            if result.memory_gb is not None and merged.memory_gb is None:
                merged.memory_gb = result.memory_gb
            
            if result.has_any_features():
                extractors_applied.append(name)
                
        except ValueError as e:
            log.warning("extractor_not_found", name=name, error=str(e))
            continue
    
    log.debug(
        "extraction_completed",
        has_features=merged.has_any_features(),
        extractors_applied=extractors_applied,
    )
    
    return merged

