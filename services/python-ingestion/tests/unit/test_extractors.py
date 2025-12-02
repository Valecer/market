"""Unit tests for feature extractors.

Tests cover:
    - ElectronicsExtractor: voltage, power, storage, memory extraction
    - DimensionsExtractor: weight, dimensions extraction
    - EXTRACTOR_REGISTRY lookup
    - extract_all_features merging
    - Edge cases and invalid values
"""
import pytest

from src.services.extraction import (
    FeatureExtractor,
    ElectronicsExtractor,
    DimensionsExtractor,
    EXTRACTOR_REGISTRY,
    create_extractor,
    extract_all_features,
)
from src.models.extraction import ExtractedFeatures, DimensionsCm


class TestElectronicsExtractor:
    """Tests for ElectronicsExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return ElectronicsExtractor()
    
    def test_get_extractor_name(self, extractor):
        """Test extractor name."""
        assert extractor.get_extractor_name() == "electronics"
    
    # Voltage extraction tests
    @pytest.mark.parametrize("text,expected", [
        ("Drill 220V Professional", 220),
        ("110V 60Hz Motor", 110),
        ("Motor 220 V AC", 220),
        ("Voltage: 240V", 240),
        ("220-240V Power Supply", 240),  # Regex finds 240V first
        ("AC 110V Adapter", 110),
        ("12V DC Power", 12),
    ])
    def test_extract_voltage(self, extractor, text, expected):
        """Test voltage extraction patterns."""
        result = extractor.extract(text)
        assert result.voltage == expected
    
    def test_extract_voltage_not_found(self, extractor):
        """Test when no voltage is found."""
        result = extractor.extract("Simple Power Tool")
        assert result.voltage is None
    
    # Power extraction tests
    @pytest.mark.parametrize("text,expected", [
        ("Drill 750W Professional", 750),
        ("1500W Heater", 1500),
        ("Power: 1.5kW", 1500),
        ("2.2 kW Motor", 2200),
        ("750 watt blender", 750),
        ("100W LED Light", 100),
    ])
    def test_extract_power(self, extractor, text, expected):
        """Test power extraction patterns."""
        result = extractor.extract(text)
        assert result.power_watts == expected
    
    def test_extract_power_not_found(self, extractor):
        """Test when no power is found."""
        result = extractor.extract("Simple Hand Tool")
        assert result.power_watts is None
    
    # Storage extraction tests
    @pytest.mark.parametrize("text,expected", [
        ("Samsung 128GB SSD", 128),
        ("256 GB HDD Drive", 256),
        ("1TB Storage", 1000),
        ("512GB NVMe M.2", 512),
        ("SSD 256GB Fast", 256),
        ("iPhone 64GB", 64),
    ])
    def test_extract_storage(self, extractor, text, expected):
        """Test storage extraction patterns."""
        result = extractor.extract(text)
        assert result.storage_gb == expected
    
    # Memory extraction tests
    @pytest.mark.parametrize("text,expected", [
        ("8GB RAM Desktop", 8),
        ("16 GB DDR4 Memory", 16),
        ("RAM 32GB DDR5", 32),
        ("4GB RAM Laptop", 4),
        ("DDR4 8GB Kit", 8),
    ])
    def test_extract_memory(self, extractor, text, expected):
        """Test memory extraction patterns."""
        result = extractor.extract(text)
        assert result.memory_gb == expected
    
    def test_extract_multiple_features(self, extractor):
        """Test extracting multiple electronics features."""
        # Use explicit SSD label which is extracted first in pattern matching
        text = "Gaming Laptop SSD 512GB 8GB RAM 220V Charger"
        result = extractor.extract(text)
        
        assert result.memory_gb == 8
        # Storage captures the SSD-labeled value (pattern: "SSD 512GB")
        assert result.storage_gb == 512
        assert result.voltage == 220


class TestDimensionsExtractor:
    """Tests for DimensionsExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return DimensionsExtractor()
    
    def test_get_extractor_name(self, extractor):
        """Test extractor name."""
        assert extractor.get_extractor_name() == "dimensions"
    
    # Weight extraction tests
    @pytest.mark.parametrize("text,expected", [
        ("Weight: 2.5kg", 2.5),
        ("2500g Package", 2.5),
        ("5.5 lbs Shipping", pytest.approx(2.495, rel=0.01)),  # ~5.5 * 0.453592
        ("1.2 kg Net Weight", 1.2),
        ("Package 500g", 0.5),
    ])
    def test_extract_weight(self, extractor, text, expected):
        """Test weight extraction patterns."""
        result = extractor.extract(text)
        assert result.weight_kg == expected
    
    def test_extract_weight_not_found(self, extractor):
        """Test when no weight is found."""
        result = extractor.extract("Lightweight Tool")
        assert result.weight_kg is None
    
    # Dimensions extraction tests
    @pytest.mark.parametrize("text,dims", [
        ("Box 30x20x10cm", (30, 20, 10)),
        ("30 x 20 x 10 cm Package", (30, 20, 10)),
        ("Size: 150x100x50 mm", (15, 10, 5)),  # mm converted to cm
        ("L30 W20 H10 cm", (30, 20, 10)),
    ])
    def test_extract_dimensions(self, extractor, text, dims):
        """Test dimensions extraction patterns."""
        result = extractor.extract(text)
        assert result.dimensions_cm is not None
        assert result.dimensions_cm.length == dims[0]
        assert result.dimensions_cm.width == dims[1]
        assert result.dimensions_cm.height == dims[2]
    
    def test_extract_dimensions_not_found(self, extractor):
        """Test when no dimensions are found."""
        result = extractor.extract("Small Box")
        assert result.dimensions_cm is None
    
    def test_extract_weight_and_dimensions(self, extractor):
        """Test extracting both weight and dimensions."""
        text = "Package 2.5kg 30x20x10cm"
        result = extractor.extract(text)
        
        assert result.weight_kg == 2.5
        assert result.dimensions_cm is not None
        assert result.dimensions_cm.length == 30


class TestExtractorRegistry:
    """Tests for EXTRACTOR_REGISTRY and factory function."""
    
    def test_registry_contains_electronics(self):
        """Test electronics extractor in registry."""
        assert "electronics" in EXTRACTOR_REGISTRY
        assert EXTRACTOR_REGISTRY["electronics"] == ElectronicsExtractor
    
    def test_registry_contains_dimensions(self):
        """Test dimensions extractor in registry."""
        assert "dimensions" in EXTRACTOR_REGISTRY
        assert EXTRACTOR_REGISTRY["dimensions"] == DimensionsExtractor
    
    def test_create_extractor_electronics(self):
        """Test factory creates electronics extractor."""
        extractor = create_extractor("electronics")
        assert isinstance(extractor, ElectronicsExtractor)
    
    def test_create_extractor_dimensions(self):
        """Test factory creates dimensions extractor."""
        extractor = create_extractor("dimensions")
        assert isinstance(extractor, DimensionsExtractor)
    
    def test_create_extractor_unknown(self):
        """Test factory raises on unknown name."""
        with pytest.raises(ValueError, match="Unknown extractor"):
            create_extractor("unknown")


class TestExtractAllFeatures:
    """Tests for extract_all_features function."""
    
    def test_extract_all_default_extractors(self):
        """Test running all extractors."""
        text = "Bosch Drill 750W 220V 2.5kg 30x20x10cm"
        result = extract_all_features(text)
        
        assert result.power_watts == 750
        assert result.voltage == 220
        assert result.weight_kg == 2.5
        assert result.dimensions_cm is not None
    
    def test_extract_all_specific_extractors(self):
        """Test running only specific extractors."""
        text = "Bosch Drill 750W 220V 2.5kg"
        result = extract_all_features(text, extractors=["electronics"])
        
        assert result.power_watts == 750
        assert result.voltage == 220
        # Dimensions extractor not run
        # Weight might not be extracted by electronics
    
    def test_extract_all_no_features(self):
        """Test when no features are found."""
        text = "Simple Product Name"
        result = extract_all_features(text)
        
        assert not result.has_any_features()
    
    def test_extract_all_merges_results(self):
        """Test that results from multiple extractors are merged."""
        text = "Samsung TV 65in 220V 15kg 145x85x5cm"
        result = extract_all_features(text)
        
        # Electronics should find voltage
        assert result.voltage == 220
        # Dimensions should find weight and dimensions
        assert result.weight_kg == 15
        assert result.dimensions_cm is not None


class TestExtractedFeaturesModel:
    """Tests for ExtractedFeatures Pydantic model."""
    
    def test_to_characteristics_empty(self):
        """Test to_characteristics with no values."""
        features = ExtractedFeatures()
        result = features.to_characteristics()
        assert result == {}
    
    def test_to_characteristics_partial(self):
        """Test to_characteristics with some values."""
        features = ExtractedFeatures(voltage=220, power_watts=750)
        result = features.to_characteristics()
        
        assert result == {"voltage": 220, "power_watts": 750}
    
    def test_to_characteristics_with_dimensions(self):
        """Test to_characteristics with dimensions."""
        features = ExtractedFeatures(
            weight_kg=2.5,
            dimensions_cm=DimensionsCm(length=30, width=20, height=10),
        )
        result = features.to_characteristics()
        
        assert result["weight_kg"] == 2.5
        assert result["dimensions_cm"] == {"length": 30, "width": 20, "height": 10}
    
    def test_has_any_features_true(self):
        """Test has_any_features returns True when has value."""
        features = ExtractedFeatures(voltage=220)
        assert features.has_any_features() is True
    
    def test_has_any_features_false(self):
        """Test has_any_features returns False when empty."""
        features = ExtractedFeatures()
        assert features.has_any_features() is False
    
    def test_validation_filters_invalid_voltage(self):
        """Test validation skips invalid voltage values."""
        features = ExtractedFeatures(voltage="TBD")
        assert features.voltage is None
    
    def test_validation_filters_invalid_power(self):
        """Test validation skips invalid power values."""
        features = ExtractedFeatures(power_watts="N/A")
        assert features.power_watts is None

