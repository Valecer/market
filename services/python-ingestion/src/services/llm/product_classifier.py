"""LLM-based product classifier for intelligent categorization.

Uses local LLM to:
- Classify products into categories
- Extract product features/characteristics
- Find similar products
- Suggest product groupings

Enhances rule-based CategoryClassifier with semantic understanding.

Example:
    classifier = LLMProductClassifier()
    result = await classifier.classify_product("Электровелосипед Shtenli Model 9...")
    # result.category = "electric_bikes"
    # result.features = {"brand": "Shtenli", "model": "Model 9", ...}
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import structlog

from .client import LLMClient, LLMConfig, get_llm_client

logger = structlog.get_logger(__name__)


@dataclass
class ExtractedFeatures:
    """Extracted product features from name/description."""
    brand: Optional[str] = None
    model: Optional[str] = None
    power: Optional[str] = None  # e.g., "250W", "500W"
    voltage: Optional[str] = None  # e.g., "48V", "60V"
    capacity: Optional[str] = None  # e.g., "12Ah", "20Ah"
    color: Optional[str] = None
    size: Optional[str] = None
    weight: Optional[str] = None
    additional: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        result = {}
        if self.brand:
            result["brand"] = self.brand
        if self.model:
            result["model"] = self.model
        if self.power:
            result["power"] = self.power
        if self.voltage:
            result["voltage"] = self.voltage
        if self.capacity:
            result["capacity"] = self.capacity
        if self.color:
            result["color"] = self.color
        if self.size:
            result["size"] = self.size
        if self.weight:
            result["weight"] = self.weight
        result.update(self.additional)
        return result


@dataclass
class ClassificationResult:
    """Result of LLM product classification."""
    category: str
    subcategory: Optional[str] = None
    confidence: float = 0.0
    features: Optional[ExtractedFeatures] = None
    reasoning: Optional[str] = None
    alternative_categories: List[Tuple[str, float]] = field(default_factory=list)
    
    @property
    def is_confident(self) -> bool:
        """Check if classification is confident enough for auto-assignment."""
        return self.confidence >= 0.7
    
    @property
    def needs_review(self) -> bool:
        """Check if classification needs human review."""
        return self.confidence < 0.5


@dataclass
class SimilarityResult:
    """Result of product similarity analysis."""
    are_similar: bool
    confidence: float
    similarity_score: float  # 0.0 - 1.0
    matching_features: List[str]
    differing_features: List[str]
    reasoning: Optional[str] = None


@dataclass
class GroupingResult:
    """Result of product grouping suggestion."""
    group_name: str
    group_key: str  # Normalized key for DB
    products: List[str]  # Product names in group
    common_features: Dict[str, Any]
    confidence: float


# Known product categories for classification
PRODUCT_CATEGORIES = {
    "electric_scooters": {
        "name_ru": "Электросамокаты",
        "keywords": ["самокат", "электросамокат", "e-scooter", "kick scooter"],
    },
    "electric_bikes": {
        "name_ru": "Электровелосипеды",
        "keywords": ["велосипед", "электровелосипед", "e-bike", "ebike"],
    },
    "electric_mopeds": {
        "name_ru": "Электроскутеры и мопеды",
        "keywords": ["скутер", "электроскутер", "мопед", "электромопед"],
    },
    "electric_trikes": {
        "name_ru": "Электротрициклы",
        "keywords": ["трицикл", "электротрицикл", "трёхколёсный"],
    },
    "garden_tillers": {
        "name_ru": "Мотоблоки и культиваторы",
        "keywords": ["мотоблок", "культиватор", "мотокультиватор"],
    },
    "mini_tractors": {
        "name_ru": "Минитракторы",
        "keywords": ["минитрактор", "трактор"],
    },
    "snow_blowers": {
        "name_ru": "Снегоуборщики",
        "keywords": ["снегоуборщик", "снегоочиститель"],
    },
    "atv": {
        "name_ru": "Квадроциклы",
        "keywords": ["квадроцикл", "atv", "utv"],
    },
    "motorcycles": {
        "name_ru": "Мотоциклы",
        "keywords": ["мотоцикл", "питбайк", "эндуро"],
    },
    "helmets": {
        "name_ru": "Шлемы",
        "keywords": ["шлем", "мотошлем", "защита"],
    },
    "spare_parts": {
        "name_ru": "Запчасти",
        "keywords": ["запчасть", "запасная часть", "деталь"],
    },
    "accessories": {
        "name_ru": "Аксессуары",
        "keywords": ["аксессуар", "кофр", "сумка", "багажник"],
    },
}

CLASSIFICATION_SYSTEM_PROMPT = """Ты - эксперт по классификации товаров для оптового каталога.
Твоя задача - определить категорию товара и извлечь его характеристики.

Доступные категории:
- electric_scooters: Электросамокаты
- electric_bikes: Электровелосипеды  
- electric_mopeds: Электроскутеры и мопеды
- electric_trikes: Электротрициклы
- garden_tillers: Мотоблоки и культиваторы
- mini_tractors: Минитракторы
- snow_blowers: Снегоуборщики
- atv: Квадроциклы
- motorcycles: Мотоциклы
- helmets: Шлемы
- spare_parts: Запчасти
- accessories: Аксессуары
- other: Другое (если не подходит ни одна категория)

Извлекай характеристики:
- brand: бренд/производитель
- model: модель
- power: мощность (в Вт или л.с.)
- voltage: напряжение (для электротранспорта)
- capacity: ёмкость батареи (Ah)
- color: цвет
- size: размер/объём
- weight: вес

Отвечай ТОЛЬКО в формате JSON."""

CLASSIFICATION_PROMPT_TEMPLATE = """Классифицируй товар и извлеки характеристики.

Название товара: {product_name}

{additional_context}

JSON формат ответа:
{{
  "category": "категория из списка",
  "subcategory": "подкатегория если есть",
  "confidence": 0.0-1.0,
  "features": {{
    "brand": "бренд или null",
    "model": "модель или null",
    "power": "мощность или null",
    "voltage": "напряжение или null",
    "capacity": "ёмкость или null",
    "color": "цвет или null"
  }},
  "reasoning": "краткое объяснение"
}}"""

SIMILARITY_SYSTEM_PROMPT = """Ты - эксперт по сравнению товаров.
Определи, являются ли два товара одним и тем же продуктом (возможно от разных поставщиков)
или разными вариантами одного продукта.

Учитывай:
- Бренд и модель
- Технические характеристики
- Различия в цвете/комплектации НЕ делают товары разными

Отвечай в формате JSON."""

SIMILARITY_PROMPT_TEMPLATE = """Сравни два товара и определи, похожи ли они.

Товар 1: {product1}
Товар 2: {product2}

JSON ответ:
{{
  "are_similar": true/false,
  "confidence": 0.0-1.0,
  "similarity_score": 0.0-1.0,
  "matching_features": ["список совпадающих характеристик"],
  "differing_features": ["список различий"],
  "reasoning": "объяснение"
}}"""

GROUPING_SYSTEM_PROMPT = """Ты - эксперт по группировке товаров для каталога.
Проанализируй список товаров и предложи группировку по общим признакам.

Группируй по:
1. Бренд + линейка моделей
2. Тип товара + характеристики
3. Категория + подкатегория

Название группы должно быть понятным для покупателя."""

GROUPING_PROMPT_TEMPLATE = """Сгруппируй эти товары по общим признакам.

Товары:
{products_list}

JSON ответ:
{{
  "groups": [
    {{
      "group_name": "Название группы",
      "group_key": "normalized_key",
      "products": ["индексы товаров в группе"],
      "common_features": {{"общие характеристики"}},
      "confidence": 0.0-1.0
    }}
  ]
}}"""


class LLMProductClassifier:
    """LLM-based product classifier.
    
    Provides intelligent product classification, feature extraction,
    and similarity analysis using local LLM.
    
    Features:
    - Category classification with confidence
    - Feature extraction (brand, model, specs)
    - Similar product detection
    - Product grouping suggestions
    
    Example:
        classifier = LLMProductClassifier()
        result = await classifier.classify_product("Электровелосипед Shtenli...")
        print(f"Category: {result.category}, Confidence: {result.confidence}")
    """
    
    def __init__(
        self,
        client: Optional[LLMClient] = None,
        config: Optional[LLMConfig] = None,
        categories: Optional[Dict[str, Dict]] = None,
    ):
        """Initialize classifier.
        
        Args:
            client: LLM client (creates default if not provided)
            config: LLM configuration
            categories: Custom category definitions
        """
        self._client = client
        self._config = config
        self.categories = categories or PRODUCT_CATEGORIES
        self._log = logger.bind(component="LLMProductClassifier")
    
    @property
    def client(self) -> LLMClient:
        """Get LLM client (lazy initialization)."""
        if self._client is None:
            self._client = get_llm_client(self._config)
        return self._client
    
    async def classify_product(
        self,
        product_name: str,
        description: Optional[str] = None,
        supplier_category: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify a product into a category.
        
        Args:
            product_name: Product name/title
            description: Optional product description
            supplier_category: Optional category from supplier
            
        Returns:
            ClassificationResult with category and features
        """
        if not product_name or not product_name.strip():
            return self._unknown_result()
        
        # Check if LLM is available
        if not await self.client.is_available():
            self._log.warning("llm_not_available_using_fallback")
            return await self._fallback_classification(product_name, supplier_category)
        
        # Build context
        context_parts = []
        if description:
            context_parts.append(f"Описание: {description}")
        if supplier_category:
            context_parts.append(f"Категория от поставщика: {supplier_category}")
        additional_context = "\n".join(context_parts) if context_parts else ""
        
        # Build prompt
        prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
            product_name=product_name,
            additional_context=additional_context,
        )
        
        try:
            response = await self.client.complete_json(
                prompt=prompt,
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
            )
            
            result = self._parse_classification_response(response)
            
            self._log.info(
                "product_classified",
                product=product_name[:50],
                category=result.category,
                confidence=result.confidence,
            )
            
            return result
            
        except Exception as e:
            self._log.error("classification_failed", error=str(e))
            return await self._fallback_classification(product_name, supplier_category)
    
    async def extract_features(
        self,
        product_name: str,
        description: Optional[str] = None,
    ) -> ExtractedFeatures:
        """Extract features from product name/description.
        
        Args:
            product_name: Product name
            description: Optional description
            
        Returns:
            ExtractedFeatures with brand, model, specs
        """
        if not await self.client.is_available():
            return self._rule_based_extraction(product_name)
        
        prompt = f"""Извлеки характеристики из названия товара.

Название: {product_name}
{f'Описание: {description}' if description else ''}

JSON ответ:
{{
  "brand": "бренд или null",
  "model": "модель или null", 
  "power": "мощность (Вт/л.с.) или null",
  "voltage": "напряжение (В) или null",
  "capacity": "ёмкость (Ah) или null",
  "color": "цвет или null",
  "size": "размер или null",
  "weight": "вес или null",
  "additional": {{}}
}}"""
        
        try:
            response = await self.client.complete_json(prompt=prompt)
            return self._parse_features(response)
        except Exception as e:
            self._log.warning("feature_extraction_failed", error=str(e))
            return self._rule_based_extraction(product_name)
    
    async def compare_products(
        self,
        product1: str,
        product2: str,
    ) -> SimilarityResult:
        """Compare two products to determine if they are similar/same.
        
        Args:
            product1: First product name
            product2: Second product name
            
        Returns:
            SimilarityResult with similarity analysis
        """
        if not await self.client.is_available():
            return self._rule_based_similarity(product1, product2)
        
        prompt = SIMILARITY_PROMPT_TEMPLATE.format(
            product1=product1,
            product2=product2,
        )
        
        try:
            response = await self.client.complete_json(
                prompt=prompt,
                system_prompt=SIMILARITY_SYSTEM_PROMPT,
            )
            
            return SimilarityResult(
                are_similar=response.get("are_similar", False),
                confidence=float(response.get("confidence", 0.5)),
                similarity_score=float(response.get("similarity_score", 0.0)),
                matching_features=response.get("matching_features", []),
                differing_features=response.get("differing_features", []),
                reasoning=response.get("reasoning"),
            )
            
        except Exception as e:
            self._log.warning("similarity_comparison_failed", error=str(e))
            return self._rule_based_similarity(product1, product2)
    
    async def suggest_groupings(
        self,
        products: List[str],
        max_groups: int = 10,
    ) -> List[GroupingResult]:
        """Suggest groupings for a list of products.
        
        Args:
            products: List of product names
            max_groups: Maximum number of groups to suggest
            
        Returns:
            List of GroupingResult with suggested groups
        """
        if not products or not await self.client.is_available():
            return []
        
        # Limit products to avoid token limits
        products_to_analyze = products[:50]
        products_list = "\n".join(
            f"{i}. {p}" for i, p in enumerate(products_to_analyze)
        )
        
        prompt = GROUPING_PROMPT_TEMPLATE.format(products_list=products_list)
        
        try:
            response = await self.client.complete_json(
                prompt=prompt,
                system_prompt=GROUPING_SYSTEM_PROMPT,
            )
            
            groups = []
            for group_data in response.get("groups", [])[:max_groups]:
                groups.append(GroupingResult(
                    group_name=group_data.get("group_name", "Unknown"),
                    group_key=group_data.get("group_key", "unknown"),
                    products=[
                        products_to_analyze[int(i)]
                        for i in group_data.get("products", [])
                        if isinstance(i, (int, str)) and int(i) < len(products_to_analyze)
                    ],
                    common_features=group_data.get("common_features", {}),
                    confidence=float(group_data.get("confidence", 0.5)),
                ))
            
            return groups
            
        except Exception as e:
            self._log.error("grouping_suggestion_failed", error=str(e))
            return []
    
    async def batch_classify(
        self,
        products: List[str],
        batch_size: int = 10,
    ) -> List[ClassificationResult]:
        """Classify multiple products efficiently.
        
        Args:
            products: List of product names
            batch_size: Products per LLM call
            
        Returns:
            List of ClassificationResult for each product
        """
        results = []
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            if await self.client.is_available():
                try:
                    batch_results = await self._classify_batch(batch)
                    results.extend(batch_results)
                    continue
                except Exception as e:
                    self._log.warning("batch_classification_failed", error=str(e))
            
            # Fallback to individual classification
            for product in batch:
                result = await self._fallback_classification(product, None)
                results.append(result)
        
        return results
    
    async def _classify_batch(self, products: List[str]) -> List[ClassificationResult]:
        """Classify a batch of products in one LLM call."""
        products_list = "\n".join(f"{i}. {p}" for i, p in enumerate(products))
        
        prompt = f"""Классифицируй эти товары.

Товары:
{products_list}

JSON ответ:
{{
  "results": [
    {{"index": 0, "category": "категория", "confidence": 0.0-1.0}},
    ...
  ]
}}"""
        
        response = await self.client.complete_json(
            prompt=prompt,
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
        )
        
        results = []
        for item in response.get("results", []):
            results.append(ClassificationResult(
                category=item.get("category", "other"),
                confidence=float(item.get("confidence", 0.5)),
            ))
        
        # Fill missing results
        while len(results) < len(products):
            results.append(self._unknown_result())
        
        return results
    
    def _parse_classification_response(
        self,
        response: Dict[str, Any],
    ) -> ClassificationResult:
        """Parse LLM response into ClassificationResult."""
        try:
            category = response.get("category", "other")
            
            # Validate category
            if category not in self.categories and category != "other":
                # Try to find closest match
                category = self._find_closest_category(category)
            
            features = None
            if "features" in response:
                features = self._parse_features(response["features"])
            
            return ClassificationResult(
                category=category,
                subcategory=response.get("subcategory"),
                confidence=float(response.get("confidence", 0.5)),
                features=features,
                reasoning=response.get("reasoning"),
            )
            
        except Exception as e:
            self._log.warning("parse_classification_failed", error=str(e))
            return self._unknown_result()
    
    def _parse_features(self, data: Dict[str, Any]) -> ExtractedFeatures:
        """Parse features from response data."""
        return ExtractedFeatures(
            brand=data.get("brand"),
            model=data.get("model"),
            power=data.get("power"),
            voltage=data.get("voltage"),
            capacity=data.get("capacity"),
            color=data.get("color"),
            size=data.get("size"),
            weight=data.get("weight"),
            additional=data.get("additional", {}),
        )
    
    def _find_closest_category(self, category: str) -> str:
        """Find closest matching category."""
        category_lower = category.lower()
        
        for key, info in self.categories.items():
            if key in category_lower or category_lower in key:
                return key
            for keyword in info.get("keywords", []):
                if keyword in category_lower:
                    return key
        
        return "other"
    
    async def _fallback_classification(
        self,
        product_name: str,
        supplier_category: Optional[str],
    ) -> ClassificationResult:
        """Rule-based fallback classification."""
        from ..classification.classifier import CategoryClassifier
        
        try:
            classifier = CategoryClassifier()
            result = classifier.classify(product_name, supplier_category)
            
            return ClassificationResult(
                category=result.category_key or "other",
                confidence=result.confidence,
                reasoning=f"Rule-based: {result.method.value}",
            )
            
        except Exception as e:
            self._log.warning("fallback_classification_failed", error=str(e))
            return self._unknown_result()
    
    def _rule_based_extraction(self, product_name: str) -> ExtractedFeatures:
        """Rule-based feature extraction."""
        import re
        
        features = ExtractedFeatures()
        name_lower = product_name.lower()
        
        # Extract brand (common brands)
        brands = [
            "shtenli", "smart balance", "kugoo", "ninebot", "xiaomi",
            "storm", "brait", "champion", "huter", "avm",
        ]
        for brand in brands:
            if brand in name_lower:
                features.brand = brand.title()
                break
        
        # Extract power
        power_match = re.search(r'(\d+)\s*[вw]т?', name_lower)
        if power_match:
            features.power = f"{power_match.group(1)}W"
        
        # Extract voltage
        voltage_match = re.search(r'(\d+)\s*[вv]', name_lower)
        if voltage_match:
            features.voltage = f"{voltage_match.group(1)}V"
        
        # Extract capacity
        capacity_match = re.search(r'(\d+)\s*[аa]h?', name_lower)
        if capacity_match:
            features.capacity = f"{capacity_match.group(1)}Ah"
        
        return features
    
    def _rule_based_similarity(
        self,
        product1: str,
        product2: str,
    ) -> SimilarityResult:
        """Rule-based similarity comparison using RapidFuzz."""
        from rapidfuzz import fuzz
        
        # Normalize names
        name1 = product1.lower().strip()
        name2 = product2.lower().strip()
        
        # Calculate similarity score
        ratio = fuzz.ratio(name1, name2) / 100.0
        partial = fuzz.partial_ratio(name1, name2) / 100.0
        token_sort = fuzz.token_sort_ratio(name1, name2) / 100.0
        
        # Weighted average
        score = (ratio * 0.3 + partial * 0.3 + token_sort * 0.4)
        
        return SimilarityResult(
            are_similar=score >= 0.7,
            confidence=0.6,  # Lower confidence for rule-based
            similarity_score=score,
            matching_features=[],
            differing_features=[],
            reasoning="Rule-based similarity using RapidFuzz",
        )
    
    def _unknown_result(self) -> ClassificationResult:
        """Return unknown classification result."""
        return ClassificationResult(
            category="other",
            confidence=0.0,
            reasoning="Unable to classify",
        )

