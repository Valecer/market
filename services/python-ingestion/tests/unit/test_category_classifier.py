"""Unit tests for CategoryClassifier.

Tests cover:
- Keyword-based classification
- Brand detection
- Supplier category fuzzy matching
- Confidence scores
- Edge cases
"""
import pytest
from uuid import uuid4

from src.services.classification import (
    CategoryClassifier,
    ClassificationResult,
)
from src.services.classification.classifier import ClassificationMethod


class TestCategoryClassifierKeywords:
    """Test keyword-based classification."""
    
    def test_iphone_classified_as_phones(self):
        """iPhone products should be classified as phones."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("iPhone 15 Pro Max 256GB черный")
        
        assert result.category_key == "phones"
        assert result.confidence >= 0.7
        assert result.method == ClassificationMethod.KEYWORD
    
    def test_smartphone_russian_keyword(self):
        """Russian 'смартфон' keyword should classify as phones."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("Смартфон Xiaomi Redmi Note 12")
        
        assert result.category_key == "phones"
        assert result.confidence >= 0.7
    
    def test_electric_scooter_classification(self):
        """Electric scooter products should be classified correctly."""
        classifier = CategoryClassifier()
        
        test_cases = [
            "Электросамокат Kugoo S3 Pro",
            "Электро самокат Ninebot Max G30",
            "E-scooter Xiaomi Mi Electric Scooter",
        ]
        
        for product_name in test_cases:
            result = classifier.classify(product_name)
            assert result.category_key in ("electric_scooters", "electrotransport"), \
                f"Failed for: {product_name}"
            assert result.confidence >= 0.6
    
    def test_motoblock_garden_equipment(self):
        """Motoblock should be classified as garden equipment."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("Мотоблок Brait BR-135DE дизель")
        
        assert result.category_key == "garden_equipment"
        assert result.confidence >= 0.7
    
    def test_quadrocycle_atv(self):
        """Quadrocycle should be classified as ATV."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("Квадроцикл CFMOTO CFORCE 600")
        
        assert result.category_key == "atv_moto"
        assert result.confidence >= 0.7
    
    def test_tablet_classification(self):
        """Tablets should be classified correctly."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("iPad Pro 12.9 M2 256GB WiFi")
        
        assert result.category_key == "tablets"
        assert result.confidence >= 0.7
    
    def test_laptop_classification(self):
        """Laptops should be classified correctly."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("MacBook Pro 14 M3 Pro 18GB 512GB")
        
        assert result.category_key == "laptops"
        assert result.confidence >= 0.7


class TestCategoryClassifierBrands:
    """Test brand-based classification."""
    
    def test_apple_default_phones(self):
        """Generic Apple products should default to phones."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("Apple 15 256GB")  # No specific keywords
        
        # Should be classified by brand as phones
        assert result.category_key == "phones"
        assert result.method == ClassificationMethod.BRAND
    
    def test_kugoo_electrotransport(self):
        """Kugoo brand should default to electric scooters."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("Kugoo M4 Pro 18Ah")
        
        assert result.category_key == "electric_scooters"
    
    def test_storm_garden_equipment(self):
        """Storm brand should default to garden equipment."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("Storm STG-700 генератор")
        
        assert result.category_key == "garden_equipment"
    
    def test_cfmoto_atv(self):
        """CFMOTO brand should default to ATV/moto."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("CFMOTO 450")
        
        assert result.category_key == "atv_moto"


class TestCategoryClassifierSupplierCategory:
    """Test supplier category fuzzy matching."""
    
    def test_exact_supplier_category_match(self):
        """Exact supplier category should match with high confidence."""
        classifier = CategoryClassifier()
        
        # Product name is ambiguous, but supplier category is clear
        result = classifier.classify(
            product_name="Model X 500",  # Ambiguous name
            supplier_category="Электротранспорт"
        )
        
        assert result.category_key == "electrotransport"
        assert result.method == ClassificationMethod.SUPPLIER_CATEGORY
    
    def test_fuzzy_supplier_category_match(self):
        """Fuzzy supplier category should match."""
        classifier = CategoryClassifier()
        
        result = classifier.classify(
            product_name="Model ABC",
            supplier_category="Электро транспорт Shtenli"  # Not exact match
        )
        
        assert result.category_key == "electrotransport"
    
    def test_supplier_category_phones(self):
        """Supplier category for phones should match."""
        classifier = CategoryClassifier()
        
        result = classifier.classify(
            product_name="Model 123",
            supplier_category="Смартфоны и телефоны"
        )
        
        assert result.category_key == "phones"


class TestCategoryClassifierConfidence:
    """Test confidence scores and thresholds."""
    
    def test_high_confidence_auto_assignable(self):
        """High confidence results should be auto-assignable."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("iPhone 15 Pro Max")
        
        assert result.is_confident  # >= 0.7
        assert not result.needs_review
    
    def test_low_confidence_needs_review(self):
        """Low confidence results should need review."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("Unknown Product XYZ")
        
        assert result.needs_review
        assert result.confidence < 0.5
    
    def test_unknown_product_returns_none(self):
        """Unknown products should return None category."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("абракадабра непонятный товар")
        
        assert result.category_key is None or result.confidence < 0.5
        assert result.method == ClassificationMethod.UNKNOWN


class TestCategoryClassifierCustomRules:
    """Test custom rules functionality."""
    
    def test_add_keyword_rule(self):
        """Adding keyword rules should work."""
        classifier = CategoryClassifier()
        
        # Initially should not match
        result1 = classifier.classify("Уникальный товар XYZ123")
        assert result1.category_key is None or "custom" not in result1.category_key
        
        # Add custom rule
        classifier.add_keyword_rule("custom_category", "уникальный товар")
        
        # Now should match
        result2 = classifier.classify("Уникальный товар XYZ123")
        assert result2.category_key == "custom_category"
    
    def test_add_brand_rule(self):
        """Adding brand rules should work."""
        classifier = CategoryClassifier()
        
        # Add custom brand
        classifier.add_brand_rule("newbrand", default_category="phones")
        
        # Should match
        result = classifier.classify("NewBrand Phone X")
        assert result.category_key == "phones"
    
    def test_custom_rules_at_init(self):
        """Custom rules at init should merge with defaults."""
        custom_keywords = {
            "custom_category": ["custom_keyword"]
        }
        
        classifier = CategoryClassifier(keyword_rules=custom_keywords)
        
        # Custom rule should work
        result1 = classifier.classify("Some custom_keyword product")
        assert result1.category_key == "custom_category"
        
        # Default rules should still work
        result2 = classifier.classify("iPhone 15")
        assert result2.category_key == "phones"


class TestCategoryClassifierEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_product_name(self):
        """Empty product name should return unknown."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("")
        
        assert result.category_key is None
        assert result.method == ClassificationMethod.UNKNOWN
    
    def test_whitespace_product_name(self):
        """Whitespace-only product name should return unknown."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("   ")
        
        assert result.category_key is None
    
    def test_mixed_case_handling(self):
        """Classification should be case-insensitive."""
        classifier = CategoryClassifier()
        
        result1 = classifier.classify("IPHONE 15")
        result2 = classifier.classify("iphone 15")
        result3 = classifier.classify("IpHoNe 15")
        
        assert result1.category_key == result2.category_key == result3.category_key == "phones"
    
    def test_special_characters_in_name(self):
        """Products with special characters should still classify."""
        classifier = CategoryClassifier()
        
        result = classifier.classify("iPhone 15 Pro Max (256GB) - черный!")
        
        assert result.category_key == "phones"
    
    def test_very_long_product_name(self):
        """Very long product names should still classify."""
        classifier = CategoryClassifier()
        
        long_name = "iPhone " + "x" * 1000 + " Pro Max"
        result = classifier.classify(long_name)
        
        assert result.category_key == "phones"
    
    def test_get_all_categories(self):
        """Should return list of all category keys."""
        classifier = CategoryClassifier()
        
        categories = classifier.get_all_categories()
        
        assert isinstance(categories, list)
        assert "phones" in categories
        assert "electrotransport" in categories
        assert "garden_equipment" in categories


class TestCategoryClassifierRealWorldProducts:
    """Test with real-world product names."""
    
    @pytest.mark.parametrize("product_name,expected_category", [
        # Phones
        ("Samsung Galaxy S24 Ultra 512GB", "phones"),
        ("Xiaomi Redmi Note 13 Pro 256GB", "phones"),
        ("Телефон HONOR X8a 128GB", "phones"),
        
        # Electric Transport
        ("Электросамокат Kugoo Kirin S4", "electric_scooters"),
        ("Электровелосипед Minako F10", "electric_bikes"),
        ("Гироскутер Smart Balance 10.5", "electrotransport"),
        
        # Garden Equipment  
        ("Мотоблок BRAIT BR-105 бензин", "garden_equipment"),
        ("Культиватор Champion GC243", "garden_equipment"),
        ("Газонокосилка Husqvarna LC 140", "garden_equipment"),
        ("Бензопила STIHL MS 180", "garden_equipment"),
        
        # ATV / Moto
        ("Квадроцикл Avantis Hunter 200", "atv_moto"),
        ("Мотоцикл Bajaj Pulsar NS200", "atv_moto"),
        ("Питбайк KAYO Basic YX125", "atv_moto"),
        
        # Accessories
        ("AirPods Pro 2nd Generation", "accessories"),
        ("Чехол для iPhone 15 Pro силиконовый", "accessories"),
        ("Наушники Sony WH-1000XM5", "accessories"),
        
        # Tablets
        ("iPad Air M1 256GB WiFi+Cellular", "tablets"),
        ("Планшет Samsung Galaxy Tab S9", "tablets"),
        
        # Laptops
        ("MacBook Air M2 13 8GB 256GB", "laptops"),
        ("Ноутбук ASUS VivoBook 15", "laptops"),
    ])
    def test_real_world_classification(self, product_name: str, expected_category: str):
        """Test classification of real-world product names."""
        classifier = CategoryClassifier()
        
        result = classifier.classify(product_name)
        
        assert result.category_key == expected_category, \
            f"Expected '{expected_category}' for '{product_name}', got '{result.category_key}'"
        assert result.confidence >= 0.5, \
            f"Low confidence {result.confidence} for '{product_name}'"

