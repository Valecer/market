"""Product name parser - extracts structured components from raw product names.

This module parses raw product names like:
    "Электровелосипед Shtenli Model Gt11 Li-ion 12 А⋅ч (48v12A) 250ВТ 25 км/ч"

Into structured components:
    - category: "Электровелосипед" → "electric_bikes"
    - brand: "Shtenli"
    - model: "Model Gt11"
    - clean_name: "Shtenli Model Gt11"
    - characteristics: "Li-ion 12 А⋅ч (48v12A) 250ВТ 25 км/ч"

Integrates with existing CategoryClassifier for category detection.
"""
import re
from typing import Optional, List, Dict, Tuple, Set
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ParsedProductName:
    """Result of parsing a product name into components."""
    original_name: str
    category_prefix: Optional[str] = None  # "Электровелосипед"
    category_key: Optional[str] = None     # "electric_bikes"
    brand: Optional[str] = None            # "Shtenli"
    model: Optional[str] = None            # "Model Gt11"
    clean_name: Optional[str] = None       # "Shtenli Model Gt11"
    characteristics: Optional[str] = None  # "Li-ion 12 А⋅ч (48v12A)..."
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage in characteristics."""
        result = {}
        if self.category_prefix:
            result['_parsed_category_prefix'] = self.category_prefix
        if self.category_key:
            result['_parsed_category_key'] = self.category_key
        if self.brand:
            result['_parsed_brand'] = self.brand
        if self.model:
            result['_parsed_model'] = self.model
        if self.clean_name:
            result['_parsed_clean_name'] = self.clean_name
        if self.characteristics:
            result['_parsed_characteristics'] = self.characteristics
        return result


class ProductNameParser:
    """Parses raw product names into structured components.
    
    Strategy:
    1. Match category prefix at start of name (e.g., "Электровелосипед")
    2. Extract brand after category prefix (e.g., "Shtenli")
    3. Extract model name (e.g., "Model Gt11", "Cruise 3", "Apache X PRO")
    4. Remaining text = characteristics
    
    Example:
        parser = ProductNameParser()
        result = parser.parse("Электровелосипед Shtenli Model Gt11 Li-ion 12A 250ВТ")
        # result.category_prefix = "Электровелосипед"
        # result.category_key = "electric_bikes"
        # result.brand = "Shtenli"
        # result.model = "Model Gt11"
        # result.clean_name = "Shtenli Model Gt11"
        # result.characteristics = "Li-ion 12A 250ВТ"
    """
    
    # Category prefixes with their category keys
    # Order matters - longer/more specific first
    CATEGORY_PREFIXES: List[Tuple[str, str]] = [
        # Electric transport - specific
        ("электровелосипед", "electric_bikes"),
        ("электросамокат", "electric_scooters"),
        ("электроскутер", "electrotransport"),
        ("электротрицикл", "electrotransport"),
        ("электромопед", "electrotransport"),
        ("электроквадроцикл", "electrotransport"),
        # General electric transport
        ("гироскутер", "electrotransport"),
        ("моноколесо", "electrotransport"),
        ("сигвей", "electrotransport"),
        # Motorcycles and ATVs
        ("квадроцикл", "atv_moto"),
        ("мотоцикл", "atv_moto"),
        ("питбайк", "atv_moto"),
        ("мопед", "atv_moto"),
        ("скутер", "atv_moto"),  # бензиновый скутер
        # Garden equipment
        ("минитрактор", "garden_equipment"),
        ("мотоблок", "garden_equipment"),
        ("культиватор", "garden_equipment"),
        ("газонокосилка", "garden_equipment"),
        ("триммер", "garden_equipment"),
        ("бензопила", "garden_equipment"),
        ("снегоуборщик", "garden_equipment"),
        ("генератор", "garden_equipment"),
        # Trailers
        ("прицеп", "trailers"),
        ("адаптер", "trailers"),
        # Protection
        ("шлем", "protection"),
        # Compound words with adjective prefix
        ("складной электровелосипед", "electric_bikes"),
        ("складной электроскутер", "electrotransport"),
        ("грузовой электрический трицикл", "electrotransport"),
        ("грузовой электротрицикл", "electrotransport"),
        ("грузовой трицикл", "electrotransport"),
    ]
    
    # Known brands (normalized to proper case)
    # NOTE: Order matters for matching - longer/compound names first
    KNOWN_BRANDS: Dict[str, str] = {
        # Electric transport
        "shtenli": "Shtenli",
        "smartbalance": "SmartBalance",
        "smart balance": "SmartBalance",
        "kugoo": "Kugoo",
        "ninebot": "Ninebot",
        "segway": "Segway",
        "kingsong": "KingSong",
        "inmotion": "InMotion",
        "gotway": "Gotway",
        "begode": "Begode",
        "avm": "AVM",
        "fedbike": "Fedbike",
        # Garden equipment
        "storm": "Storm",
        "brait": "Brait",
        "champion": "Champion",
        "huter": "Huter",
        "patriot": "Patriot",
        "carver": "Carver",
        "husqvarna": "Husqvarna",
        "stihl": "Stihl",
        "branson": "Branson",
        # Note: Grizlik, Hummer, Apache are MODEL names (under AVM brand), not brands
    }
    
    # Model patterns - what comes after brand name
    # These help identify where model name ends and characteristics begin
    MODEL_PATTERNS = [
        # Explicit model indicators
        r'Model\s*\d+\w*',           # "Model 9", "Model Gt11", "Model 100"
        r'Model\s+\w+',              # "Model Long Range"
        r'Cruise\s*\d+',             # "Cruise 3"
        r'Trike\s+\w+',              # "Trike xMax"
        r'Allroad\s+\w+',            # "Allroad PCX10"
        # AVM model names
        r'Grizlik\s*\d*\s*\w*',      # "Grizlik 49 MAX", "Grizlik"
        r'Hummer\s*\d*',             # "Hummer 200"
        r'Apache\s*\w*\s*PRO',       # "Apache X PRO"
        r'Apache\s*\w+',             # "Apache Y"
        # Pro/Max/Plus variants
        r'\w+\s*PRO(?:\s|$)',        # "HP-1900 PRO"
        r'\w+\s*MAX(?:\s|$)',        # "49 MAX"
        r'\w+\s*PLUS(?:\s|$)',
        r'\w+\s*LITE(?:\s|$)',       # "City LITE"
        # Alphanumeric codes
        r'[A-Z]{2,3}[-\s]?\d{3,4}',  # "PCX10", "GTR 48", "RKS 36"
        r'[A-Z]+\d+[A-Z]*',          # "GT11", "Y48", "X13"
        r'\d+\s*[A-Z]+',             # "49 MAX", "200 PRO"
        # Product line names
        r'City\s+\w+',               # "City LITE"
        r'Fermer',                   # "Fermer"
        r'HUNTER',                   # "HUNTER"
        r'Tank\s+\w+',               # "Tank Mini"
        r'Master\s+\d+',             # "Master 2025"
        r'Long\s+Range',             # "Long Range"
        r'Быстросъем',               # "Быстросъем" (quick release)
        r'BYSEL',                    # "BYSEL" product
    ]
    
    # Characteristic indicators - text after these is definitely characteristics
    CHARACTERISTIC_INDICATORS = [
        r'Li[-\s]?ion',              # Battery type
        r'LI[-\s]?ION',
        r'\d+\s*[Аа][·⋅]?[Чч]',      # Amp-hours: "12 А⋅ч", "12Ач"
        r'\d+[Vv]\d+[Aa]',           # Voltage/Amps: "48v12A"
        r'\(\d+[vVвВ]',              # "(48v", "(36В"
        r'\d+\s*[Вв][Тт]',           # Power: "250Вт", "250 Вт"
        r'\d+\s*[Ww](?:att)?',       # Power: "250W", "250Watt"
        r'\d+\s*км/ч',               # Speed: "25 км/ч"
        r'\d+\s*л\.?с',              # Horsepower: "18 л.с"
        r'Внимание',                 # Attention notices
        r'новинка',                  # "новинка!" tag
        r'ЛИТИЕВАЯ',                 # Battery type
        r'на литье',                 # Wheel type
        r'на спицах',                # Wheel type
        r'номинальная',              # Power rating
        r'не требу',                 # License requirements
        # Colors - usually come at the end as characteristics
        r'\s[Бб]елый(?:\s|$)',       # White
        r'\s[Чч]ерный(?:\s|$)',      # Black
        r'\s[Кк]расный(?:\s|$)',     # Red
        r'\s[Сс]иний(?:\s|$)',       # Blue
        r'\s[Зз]еленый(?:\s|$)',     # Green
        r'\s[Жж]елтый(?:\s|$)',      # Yellow
        r'\s[Сс]ерый(?:\s|$)',       # Gray
        r'\s[Зз]олотой(?:\s|$)',     # Gold
        r'\s[Оо]ранжевый(?:\s|$)',   # Orange
    ]
    
    def __init__(self):
        """Initialize parser with compiled patterns."""
        self._log = logger.bind(component="ProductNameParser")
        
        # Compile patterns
        self._model_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.MODEL_PATTERNS
        ]
        self._char_indicators = [
            re.compile(p, re.IGNORECASE) for p in self.CHARACTERISTIC_INDICATORS
        ]
        
        # Sort category prefixes by length (longest first)
        self._sorted_prefixes = sorted(
            self.CATEGORY_PREFIXES,
            key=lambda x: len(x[0]),
            reverse=True
        )
    
    def parse(self, raw_name: str) -> ParsedProductName:
        """Parse a raw product name into structured components.
        
        Args:
            raw_name: Full product name string
            
        Returns:
            ParsedProductName with extracted components
        """
        if not raw_name or not raw_name.strip():
            return ParsedProductName(original_name=raw_name or "")
        
        result = ParsedProductName(original_name=raw_name)
        remaining = raw_name.strip()
        
        # Step 1: Extract category prefix
        category_prefix, category_key, remaining = self._extract_category_prefix(remaining)
        result.category_prefix = category_prefix
        result.category_key = category_key
        
        # Step 2: Extract brand
        brand, remaining = self._extract_brand(remaining)
        result.brand = brand
        
        # Step 3: Extract model name
        model, characteristics = self._extract_model_and_characteristics(remaining, brand)
        result.model = model
        result.characteristics = characteristics
        
        # Step 4: Build clean name
        result.clean_name = self._build_clean_name(brand, model)
        
        self._log.debug(
            "name_parsed",
            original=raw_name[:60],
            category=category_key,
            brand=brand,
            model=model,
            clean_name=result.clean_name,
        )
        
        return result
    
    def _extract_category_prefix(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """Extract category prefix from beginning of text.
        
        Returns:
            (category_prefix, category_key, remaining_text)
        """
        text_lower = text.lower()
        
        for prefix, category_key in self._sorted_prefixes:
            if text_lower.startswith(prefix):
                # Extract the actual prefix (preserving original case)
                actual_prefix = text[:len(prefix)]
                remaining = text[len(prefix):].strip()
                return actual_prefix, category_key, remaining
        
        return None, None, text
    
    def _extract_brand(self, text: str) -> Tuple[Optional[str], str]:
        """Extract brand name from text.
        
        Returns:
            (brand_name, remaining_text)
        """
        text_lower = text.lower()
        
        # Find brand at start of text
        for brand_key, brand_proper in self.KNOWN_BRANDS.items():
            if text_lower.startswith(brand_key):
                remaining = text[len(brand_key):].strip()
                return brand_proper, remaining
        
        # Try finding brand anywhere in first part of text
        # (handles cases like "Складной Shtenli...")
        words = text.split()
        for i, word in enumerate(words[:3]):  # Check first 3 words
            word_lower = word.lower()
            for brand_key, brand_proper in self.KNOWN_BRANDS.items():
                if word_lower == brand_key or word_lower.startswith(brand_key):
                    # Found brand - remaining is everything after it
                    remaining = ' '.join(words[i+1:])
                    return brand_proper, remaining
        
        return None, text
    
    def _extract_model_and_characteristics(
        self,
        text: str,
        brand: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract model name and characteristics from remaining text.
        
        Strategy:
        1. Find where characteristics begin (using indicator patterns)
        2. Everything before = model name
        3. Everything after = characteristics
        
        Returns:
            (model_name, characteristics)
        """
        if not text:
            return None, None
        
        # Find earliest characteristic indicator
        char_start = len(text)
        for pattern in self._char_indicators:
            match = pattern.search(text)
            if match and match.start() < char_start:
                char_start = match.start()
        
        if char_start == 0:
            # Characteristics start immediately - no model name
            return None, text.strip()
        
        if char_start < len(text):
            # Split at characteristic indicator
            model_part = text[:char_start].strip()
            char_part = text[char_start:].strip()
            return model_part if model_part else None, char_part if char_part else None
        
        # No characteristic indicators found - try model patterns
        best_model = None
        best_end = 0
        
        for pattern in self._model_patterns:
            match = pattern.search(text)
            if match:
                # Take the longest match
                if match.end() > best_end:
                    best_model = match.group().strip()
                    best_end = match.end()
        
        if best_model:
            # Model found - check if there's more after it
            remaining = text[best_end:].strip()
            if remaining:
                return best_model, remaining
            return best_model, None
        
        # No clear split found - use heuristics
        # If text is short, assume it's all model name
        if len(text) < 30:
            return text.strip(), None
        
        # Otherwise, first word(s) are model, rest is characteristics
        words = text.split()
        if len(words) <= 2:
            return text.strip(), None
        
        # Take first 2 words as model
        return ' '.join(words[:2]), ' '.join(words[2:])
    
    def _build_clean_name(
        self,
        brand: Optional[str],
        model: Optional[str]
    ) -> Optional[str]:
        """Build clean product name from brand and model."""
        parts = []
        if brand:
            parts.append(brand)
        if model:
            parts.append(model)
        
        return ' '.join(parts) if parts else None
    
    def add_brand(self, brand_key: str, brand_proper: str) -> None:
        """Add a brand to the known brands list.
        
        Args:
            brand_key: Lowercase brand key for matching
            brand_proper: Properly capitalized brand name
        """
        self.KNOWN_BRANDS[brand_key.lower()] = brand_proper
    
    def add_category_prefix(self, prefix: str, category_key: str) -> None:
        """Add a category prefix.
        
        Args:
            prefix: Lowercase prefix to match
            category_key: Category key to assign
        """
        self._sorted_prefixes.append((prefix.lower(), category_key))
        self._sorted_prefixes.sort(key=lambda x: len(x[0]), reverse=True)


# Convenience function
def parse_product_name(raw_name: str) -> ParsedProductName:
    """Parse a product name into structured components.
    
    Args:
        raw_name: Full product name string
        
    Returns:
        ParsedProductName with extracted components
    """
    parser = ProductNameParser()
    return parser.parse(raw_name)

