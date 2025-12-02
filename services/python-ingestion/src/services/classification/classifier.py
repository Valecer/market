"""Product category classifier using keyword and brand rules.

This module provides intelligent product categorization that works
independently of supplier spreadsheet structure.

Strategy:
1. Keyword matching in product name (highest priority)
2. Brand detection with brand-specific rules
3. Supplier category fallback (fuzzy match)
4. Unknown → manual review queue

Example:
    classifier = CategoryClassifier()
    result = classifier.classify("iPhone 15 Pro Max 256GB черный")
    # result.category_key = "phones"
    # result.confidence = 0.9
    # result.method = "keyword"
"""
import re
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import structlog

from rapidfuzz import fuzz

logger = structlog.get_logger(__name__)


class ClassificationMethod(str, Enum):
    """How the category was determined."""
    KEYWORD = "keyword"
    BRAND = "brand"
    SUPPLIER_CATEGORY = "supplier_category"
    FUZZY_MATCH = "fuzzy_match"
    UNKNOWN = "unknown"


@dataclass
class CategoryRule:
    """A classification rule."""
    category_key: str
    pattern: str
    priority: int = 100
    is_regex: bool = False


@dataclass
class ClassificationResult:
    """Result of product classification."""
    category_key: Optional[str]
    confidence: float  # 0.0 - 1.0
    method: ClassificationMethod
    matched_pattern: Optional[str] = None
    all_matches: List[Tuple[str, float]] = field(default_factory=list)
    
    @property
    def is_confident(self) -> bool:
        """Returns True if confidence is high enough for auto-assignment."""
        return self.confidence >= 0.7
    
    @property
    def needs_review(self) -> bool:
        """Returns True if classification needs human review."""
        return self.category_key is None or self.confidence < 0.5


class CategoryClassifier:
    """Rule-based product category classifier.
    
    Uses keyword matching and brand detection to classify products
    independently of supplier spreadsheet organization.
    
    Attributes:
        keyword_rules: Dict mapping category keys to keyword lists
        brand_rules: Dict mapping brand names to category keys
        category_synonyms: Dict mapping category keys to known synonyms
    """
    
    # Keyword rules: category_key → list of keywords
    # Keywords are checked in product name (case-insensitive)
    DEFAULT_KEYWORD_RULES: Dict[str, List[str]] = {
        # Electronics - Phones
        "phones": [
            "iphone", "смартфон", "телефон", "samsung galaxy", "pixel",
            "xiaomi mi", "redmi note", "poco", "huawei p", "honor",
            "oneplus", "realme", "oppo", "vivo", "nothing phone",
            "мобильный телефон", "сотовый",
        ],
        
        # Electronics - Tablets (longer patterns to beat phone keywords)
        "tablets": [
            "планшет samsung", "планшет xiaomi", "планшет huawei",
            "планшет lenovo", "планшет apple", "galaxy tab s",
            "планшет", "ipad pro", "ipad air", "ipad mini", "ipad",
            "tablet", "galaxy tab", "xiaomi pad", "huawei matepad",
            "lenovo tab", "tab s", "mediapad",
        ],
        
        # Electronics - Laptops
        "laptops": [
            "macbook", "ноутбук", "laptop", "ultrabook", "thinkpad",
            "ideapad", "vivobook", "zenbook", "swift", "aspire",
        ],
        
        # Electronics - Accessories (longer patterns to beat phone keywords)
        "accessories": [
            "чехол для iphone", "чехол для samsung", "чехол для xiaomi",
            "чехол для", "чехол на", "airpods", "наушники беспроводные",
            "наушники", "зарядное устройство", "зарядка", "кабель usb",
            "кабель type-c", "кабель lightning", "кабель", "powerbank",
            "power bank", "защитное стекло", "пленка защитная", "пленка",
            "чехол",  # Short version as fallback
        ],
        
        # Electric Scooters (more specific - checked first due to priority)
        "electric_scooters": [
            "электросамокат", "e-scooter", "kick scooter electric",
            "самокат электрический", "electric kick scooter",
        ],
        
        # Electric Bikes (more specific)
        "electric_bikes": [
            "электровелосипед", "e-bike", "велосипед электрический",
            "электробайк", "electric bike", "ebike",
        ],
        
        # Electric Transport (general - includes gyroscooters, monowheels)
        "electrotransport": [
            "электроскутер", "электротрицикл", "электромопед",
            "гироскутер", "моноколесо", "сигвей", "segway",
            "электротранспорт", "electric transport",
        ],
        
        # Garden Equipment
        "garden_equipment": [
            "мотоблок", "культиватор", "минитрактор", "трактор",
            "газонокосилка", "триммер", "бензопила", "мотокоса",
            "снегоуборщик", "мотопомпа", "генератор", "компрессор",
        ],
        
        # ATVs and Motorcycles
        "atv_moto": [
            "квадроцикл", "мотоцикл", "питбайк", "эндуро",
            "мопед", "скутер бензиновый", "atv", "utv",
        ],
        
        # Trailers and Attachments
        "trailers": [
            "прицеп", "адаптер", "навесное оборудование", "плуг",
            "окучник", "фреза", "косилка", "картофелекопалка",
        ],
        
        # Helmets and Protection
        "protection": [
            "шлем", "защита", "мотошлем", "наколенники", "налокотники",
            "мотоперчатки", "мотоботы", "мотокуртка",
        ],
        
        # Spare Parts
        "spare_parts": [
            "запчасть", "запчасти", "деталь", "ремкомплект",
            "фильтр", "свеча", "ремень", "цепь", "звезда",
        ],
    }
    
    # Brand rules: brand_name → (default_category, product_type_overrides)
    # Some brands need product type detection (e.g., Xiaomi makes phones AND scooters)
    DEFAULT_BRAND_RULES: Dict[str, Dict] = {
        # Apple - mostly phones/tablets/laptops
        "apple": {"default": "phones", "keywords": {
            "macbook": "laptops",
            "ipad": "tablets",
            "airpods": "accessories",
            "watch": "accessories",
        }},
        "iphone": {"default": "phones"},
        
        # Samsung - phones, tablets, TVs, appliances
        "samsung": {"default": None, "keywords": {  # None = needs keyword match
            "galaxy s": "phones",
            "galaxy a": "phones",
            "galaxy z": "phones",
            "galaxy tab": "tablets",
        }},
        
        # Xiaomi - phones, scooters, everything
        "xiaomi": {"default": None, "keywords": {
            "mi ": "phones",
            "redmi": "phones",
            "poco": "phones",
            "mi electric scooter": "electric_scooters",
            "mi scooter": "electric_scooters",
        }},
        
        # Electric transport brands
        "kugoo": {"default": "electric_scooters"},
        "ninebot": {"default": "electric_scooters"},
        "segway": {"default": "electrotransport"},
        "smart balance": {"default": "electrotransport"},
        "smartbalance": {"default": "electrotransport"},
        "shtenli": {"default": "electrotransport"},
        "kingsong": {"default": "electrotransport"},
        "inmotion": {"default": "electrotransport"},
        "gotway": {"default": "electrotransport"},
        "begode": {"default": "electrotransport"},
        
        # Garden equipment brands
        "storm": {"default": "garden_equipment"},
        "brait": {"default": "garden_equipment"},
        "champion": {"default": "garden_equipment"},
        "huter": {"default": "garden_equipment"},
        "patriot": {"default": "garden_equipment"},
        "carver": {"default": "garden_equipment"},
        "husqvarna": {"default": "garden_equipment"},
        "stihl": {"default": "garden_equipment"},
        
        # ATV brands
        "cfmoto": {"default": "atv_moto"},
        "stels": {"default": "atv_moto"},
        "avantis": {"default": "atv_moto"},
    }
    
    # Category synonyms for fuzzy matching supplier categories
    DEFAULT_CATEGORY_SYNONYMS: Dict[str, List[str]] = {
        "electrotransport": [
            "электротранспорт", "электро транспорт", "электро-транспорт",
            "электрический транспорт", "electric transport",
        ],
        "electric_scooters": [
            "электросамокаты", "электро самокаты", "электро-самокаты",
            "самокаты электрические", "e-scooters",
        ],
        "electric_bikes": [
            "электровелосипеды", "электро велосипеды", "e-bikes",
            "велосипеды электрические",
        ],
        "garden_equipment": [
            "мотоблоки", "мотоблоки и минитракторы", "садовая техника",
            "сельхозтехника", "garden equipment",
        ],
        "phones": [
            "телефоны", "смартфоны", "мобильные телефоны", "phones",
            "smartphones", "сотовые телефоны",
        ],
        "atv_moto": [
            "квадроциклы", "мотоциклы", "мототехника", "atv", "мото",
        ],
    }
    
    def __init__(
        self,
        keyword_rules: Optional[Dict[str, List[str]]] = None,
        brand_rules: Optional[Dict[str, Dict]] = None,
        category_synonyms: Optional[Dict[str, List[str]]] = None,
    ):
        """Initialize classifier with rules.
        
        Args:
            keyword_rules: Custom keyword rules (merged with defaults)
            brand_rules: Custom brand rules (merged with defaults)
            category_synonyms: Custom category synonyms (merged with defaults)
        """
        self.keyword_rules = {**self.DEFAULT_KEYWORD_RULES}
        if keyword_rules:
            self.keyword_rules.update(keyword_rules)
        
        self.brand_rules = {**self.DEFAULT_BRAND_RULES}
        if brand_rules:
            self.brand_rules.update(brand_rules)
        
        self.category_synonyms = {**self.DEFAULT_CATEGORY_SYNONYMS}
        if category_synonyms:
            self.category_synonyms.update(category_synonyms)
        
        self._log = logger.bind(component="CategoryClassifier")
    
    def classify(
        self,
        product_name: str,
        supplier_category: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify a product into a category.
        
        Args:
            product_name: Product name/title to classify
            supplier_category: Optional category from supplier spreadsheet
            
        Returns:
            ClassificationResult with category and confidence
        """
        name_lower = product_name.lower().strip()
        all_matches: List[Tuple[str, float]] = []
        
        # Strategy 1: Keyword matching (highest confidence)
        keyword_result = self._match_keywords(name_lower)
        if keyword_result:
            category_key, confidence, pattern = keyword_result
            all_matches.append((category_key, confidence))
            
            if confidence >= 0.6:
                self._log.debug(
                    "classified_by_keyword",
                    product=product_name[:50],
                    category=category_key,
                    pattern=pattern,
                    confidence=confidence,
                )
                return ClassificationResult(
                    category_key=category_key,
                    confidence=confidence,
                    method=ClassificationMethod.KEYWORD,
                    matched_pattern=pattern,
                    all_matches=all_matches,
                )
        
        # Strategy 2: Brand detection
        brand_result = self._match_brand(name_lower)
        if brand_result:
            category_key, confidence, brand = brand_result
            all_matches.append((category_key, confidence))
            
            if confidence >= 0.5:
                self._log.debug(
                    "classified_by_brand",
                    product=product_name[:50],
                    category=category_key,
                    brand=brand,
                    confidence=confidence,
                )
                return ClassificationResult(
                    category_key=category_key,
                    confidence=confidence,
                    method=ClassificationMethod.BRAND,
                    matched_pattern=brand,
                    all_matches=all_matches,
                )
        
        # Strategy 3: Supplier category fuzzy match
        if supplier_category:
            fuzzy_result = self._fuzzy_match_supplier_category(supplier_category)
            if fuzzy_result:
                category_key, confidence = fuzzy_result
                all_matches.append((category_key, confidence))
                
                if confidence >= 0.5:
                    self._log.debug(
                        "classified_by_supplier_category",
                        product=product_name[:50],
                        category=category_key,
                        supplier_category=supplier_category,
                        confidence=confidence,
                    )
                    return ClassificationResult(
                        category_key=category_key,
                        confidence=confidence,
                        method=ClassificationMethod.SUPPLIER_CATEGORY,
                        matched_pattern=supplier_category,
                        all_matches=all_matches,
                    )
        
        # No confident match found
        self._log.debug(
            "classification_uncertain",
            product=product_name[:50],
            supplier_category=supplier_category,
            all_matches=all_matches,
        )
        
        # Return best guess if any matches found
        if all_matches:
            best_match = max(all_matches, key=lambda x: x[1])
            return ClassificationResult(
                category_key=best_match[0],
                confidence=best_match[1],
                method=ClassificationMethod.FUZZY_MATCH,
                all_matches=all_matches,
            )
        
        return ClassificationResult(
            category_key=None,
            confidence=0.0,
            method=ClassificationMethod.UNKNOWN,
            all_matches=all_matches,
        )
    
    def _match_keywords(self, name_lower: str) -> Optional[Tuple[str, float, str]]:
        """Match product name against keyword rules.
        
        Prioritizes longer, more specific keywords for better classification.
        For example, "электросамокат" (14 chars) takes priority over
        "самокат" (7 chars) to get more specific category.
        
        Returns:
            (category_key, confidence, matched_keyword) or None
        """
        all_matches: List[Tuple[str, float, str, int]] = []  # (category, confidence, keyword, keyword_len)
        
        for category_key, keywords in self.keyword_rules.items():
            for keyword in keywords:
                if keyword in name_lower:
                    keyword_len = len(keyword)
                    
                    # Base confidence
                    confidence = 0.7
                    
                    # Bonus for longer keywords (more specific)
                    if keyword_len >= 15:
                        confidence += 0.2
                    elif keyword_len >= 10:
                        confidence += 0.15
                    elif keyword_len >= 7:
                        confidence += 0.1
                    
                    # Bonus if keyword is at start of name
                    if name_lower.startswith(keyword):
                        confidence += 0.1
                    
                    confidence = min(confidence, 1.0)
                    
                    all_matches.append((category_key, confidence, keyword, keyword_len))
        
        if not all_matches:
            return None
        
        # Sort by keyword length (longer = more specific), then by confidence
        all_matches.sort(key=lambda x: (x[3], x[1]), reverse=True)
        
        best = all_matches[0]
        return (best[0], best[1], best[2])
    
    def _match_brand(self, name_lower: str) -> Optional[Tuple[str, float, str]]:
        """Match product name against brand rules.
        
        Returns:
            (category_key, confidence, brand_name) or None
        """
        for brand, rules in self.brand_rules.items():
            if brand not in name_lower:
                continue
            
            # Brand found - check for product type overrides
            if "keywords" in rules:
                for keyword, category in rules["keywords"].items():
                    if keyword in name_lower:
                        return (category, 0.8, brand)
            
            # Use default category for brand
            default_category = rules.get("default")
            if default_category:
                return (default_category, 0.6, brand)
        
        return None
    
    def _fuzzy_match_supplier_category(
        self,
        supplier_category: str
    ) -> Optional[Tuple[str, float]]:
        """Fuzzy match supplier category against known synonyms.
        
        Returns:
            (category_key, confidence) or None
        """
        supplier_lower = supplier_category.lower().strip()
        
        best_match: Optional[Tuple[str, float]] = None
        
        for category_key, synonyms in self.category_synonyms.items():
            for synonym in synonyms:
                # Try exact match first
                if synonym == supplier_lower:
                    return (category_key, 0.95)
                
                # Try fuzzy match
                score = fuzz.ratio(supplier_lower, synonym) / 100.0
                
                if score >= 0.7:
                    if best_match is None or score > best_match[1]:
                        best_match = (category_key, score * 0.9)  # Slightly reduce for fuzzy
        
        return best_match
    
    def add_keyword_rule(self, category_key: str, keyword: str) -> None:
        """Add a keyword rule at runtime.
        
        Args:
            category_key: Target category
            keyword: Keyword to match (case-insensitive)
        """
        if category_key not in self.keyword_rules:
            self.keyword_rules[category_key] = []
        
        keyword_lower = keyword.lower()
        if keyword_lower not in self.keyword_rules[category_key]:
            self.keyword_rules[category_key].append(keyword_lower)
    
    def add_brand_rule(
        self,
        brand: str,
        default_category: Optional[str] = None,
        keywords: Optional[Dict[str, str]] = None
    ) -> None:
        """Add a brand rule at runtime.
        
        Args:
            brand: Brand name (case-insensitive)
            default_category: Default category for this brand
            keywords: Product type keyword overrides
        """
        brand_lower = brand.lower()
        self.brand_rules[brand_lower] = {
            "default": default_category,
        }
        if keywords:
            self.brand_rules[brand_lower]["keywords"] = {
                k.lower(): v for k, v in keywords.items()
            }
    
    def get_all_categories(self) -> List[str]:
        """Get list of all known category keys."""
        categories = set(self.keyword_rules.keys())
        categories.update(self.category_synonyms.keys())
        return sorted(categories)

