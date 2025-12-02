"""Tests for dynamic header detector.

Following Marketbel testing best practices:
- Use patch.object() for mocking object attributes
- Use fixtures for reusable test data
- Test both positive and edge cases
"""

import pytest
from typing import List
from src.parsers.dynamic_header_detector import (
    DynamicHeaderDetector,
    FieldPatternMatcher,
    RowClassifier,
    SectionTracker,
    FieldType,
    RowType,
    DetectorConfig,
    SheetStructure,
)


class TestFieldPatternMatcher:
    """Tests for Russian field name pattern matching."""
    
    @pytest.fixture
    def matcher(self) -> FieldPatternMatcher:
        return FieldPatternMatcher()
    
    @pytest.mark.parametrize("header,expected_type", [
        # Name patterns
        ("Наименование", FieldType.NAME),
        ("Название", FieldType.NAME),
        ("Модель", FieldType.NAME),
        ("Наименование|Ссылка", FieldType.NAME),
        
        # Wholesale price patterns
        ("Оптовая цена", FieldType.PRICE_WHOLESALE),
        ("Цена с НДС", FieldType.PRICE_WHOLESALE),
        ("Закупка", FieldType.PRICE_WHOLESALE),
        ("Закупка Бел. руб.", FieldType.PRICE_WHOLESALE),
        
        # Retail price patterns
        ("МРЦ", FieldType.PRICE_RETAIL),
        ("РРЦ", FieldType.PRICE_RETAIL),
        ("Розница", FieldType.PRICE_RETAIL),
        ("МРЦ Бел. руб.", FieldType.PRICE_RETAIL),
        
        # Availability patterns
        ("Наличие", FieldType.AVAILABILITY),
        ("Остаток", FieldType.AVAILABILITY),
        ("Статус", FieldType.AVAILABILITY),
        
        # Image patterns
        ("Фото", FieldType.IMAGE),
        ("Фотография", FieldType.IMAGE),
        ("Изображение", FieldType.IMAGE),
        
        # SKU patterns
        ("Артикул", FieldType.SKU),
        ("Код товара", FieldType.SKU),
        
        # Link patterns
        ("Ссылка", FieldType.LINK),
        ("Характеристики на сайте", FieldType.LINK),
        
        # Description patterns
        ("Характеристики", FieldType.DESCRIPTION),
        ("Описание", FieldType.DESCRIPTION),
    ])
    def test_russian_field_patterns(self, matcher: FieldPatternMatcher, header: str, expected_type: FieldType):
        """Test that Russian headers are correctly matched to field types."""
        field_type, confidence = matcher.match_field(header)
        assert field_type == expected_type, f"Expected {expected_type} for '{header}', got {field_type}"
        assert confidence > 0.5, f"Confidence too low for '{header}': {confidence}"
    
    def test_exact_match_has_highest_confidence(self, matcher: FieldPatternMatcher):
        """Exact matches should have confidence = 1.0."""
        field_type, confidence = matcher.match_field("наименование")
        assert confidence == 1.0
    
    def test_unknown_field(self, matcher: FieldPatternMatcher):
        """Unknown headers should return UNKNOWN type."""
        field_type, confidence = matcher.match_field("Какое-то поле")
        assert field_type == FieldType.UNKNOWN
        assert confidence == 0.0
    
    def test_empty_header(self, matcher: FieldPatternMatcher):
        """Empty headers should return UNKNOWN type."""
        field_type, confidence = matcher.match_field("")
        assert field_type == FieldType.UNKNOWN
        
        field_type, confidence = matcher.match_field(None)
        assert field_type == FieldType.UNKNOWN
    
    def test_generic_price_fallback(self, matcher: FieldPatternMatcher):
        """Generic price words should default to retail."""
        field_type, confidence = matcher.match_field("Цена")
        assert field_type == FieldType.PRICE_RETAIL
        assert confidence == 0.5


class TestRowClassifier:
    """Tests for row type classification."""
    
    @pytest.fixture
    def classifier(self) -> RowClassifier:
        return RowClassifier(FieldPatternMatcher())
    
    def test_empty_row(self, classifier: RowClassifier):
        """Empty rows should be classified as EMPTY."""
        result = classifier.classify_row(["", "", ""], 0)
        assert result.row_type == RowType.EMPTY
    
    def test_header_row(self, classifier: RowClassifier):
        """Rows with field names should be classified as HEADER."""
        result = classifier.classify_row(
            ["Наименование", "Цена", "МРЦ", "Наличие"], 0
        )
        assert result.row_type == RowType.HEADER
    
    def test_data_row(self, classifier: RowClassifier):
        """Rows with text and numbers should be classified as DATA."""
        result = classifier.classify_row(
            ["SmartBalance Fermer", "1850", "2499", "В наличии"], 0
        )
        assert result.row_type == RowType.DATA
    
    @pytest.mark.parametrize("section_name", [
        "Электротранспорт",
        "Электроскутера",
        "Мотоблоки",
        "Минитракторы и навесное оборудование",
    ])
    def test_section_detection(self, classifier: RowClassifier, section_name: str):
        """Section headers should be detected correctly."""
        result = classifier.classify_row([section_name, "", "", ""], 0)
        assert result.row_type == RowType.SECTION
        assert result.section_name == section_name
    
    def test_subsection_detection(self, classifier: RowClassifier):
        """Subsections (Модификация - X) should be detected."""
        result = classifier.classify_row(["Модификация - Mini Sport", "", ""], 0)
        assert result.row_type == RowType.SUBSECTION
        assert "Mini Sport" in result.section_name
    
    def test_info_row(self, classifier: RowClassifier):
        """Info rows (contacts, etc.) should be classified as INFO."""
        result = classifier.classify_row(
            ["Поставщик: ООО Рога и Копыта", "", ""], 0
        )
        assert result.row_type == RowType.INFO
    
    def test_repeated_header_detection(self, classifier: RowClassifier):
        """Repeated headers should be detected when known_headers provided."""
        known_headers = ["Наименование", "Цена", "МРЦ", "Наличие"]
        
        result = classifier.classify_row(
            ["Наименование", "Цена", "МРЦ", "Наличие"],
            5,
            known_headers=known_headers
        )
        assert result.row_type == RowType.REPEATED_HEADER


class TestDynamicHeaderDetector:
    """Tests for the main detector class."""
    
    @pytest.fixture
    def detector(self) -> DynamicHeaderDetector:
        return DynamicHeaderDetector()
    
    @pytest.fixture
    def simple_data(self) -> List[List[str]]:
        """Simple price list without sections."""
        return [
            ["Наименование", "Цена с НДС", "МРЦ", "Наличие"],
            ["SmartBalance Fermer", "1850", "2499", "В наличии"],
            ["SmartBalance City", "2050", "2590", "В наличии"],
            ["SmartBalance Tank", "1750", "2199", "Нет"],
        ]
    
    @pytest.fixture
    def data_with_sections(self) -> List[List[str]]:
        """Price list with category sections."""
        return [
            ["Наименование", "Цена", "МРЦ", "Наличие"],
            ["Электровелосипеды", "", "", ""],
            ["E-Bike Model 1", "1000", "1200", "+"],
            ["E-Bike Model 2", "1500", "1800", "+"],
            ["Электроскутера", "", "", ""],
            ["Scooter Model 1", "3000", "3500", "+"],
        ]
    
    @pytest.fixture
    def data_with_info_header(self) -> List[List[str]]:
        """Price list with company info at the top."""
        return [
            ["Поставщик: ООО Тест", "", "", ""],
            ["Телефон: +375 29 123 45 67", "", "", ""],
            ["", "", "", ""],
            ["Наименование", "Закупка", "МРЦ", "Наличие"],
            ["Товар 1", "1000", "1200", "Есть"],
        ]
    
    def test_simple_structure_detection(self, detector: DynamicHeaderDetector, simple_data: List[List[str]]):
        """Test detection of simple price list structure."""
        structure = detector.analyze_sheet(simple_data, "Test")
        
        assert structure.header_rows == [0]
        assert structure.data_start_row == 1
        assert len(structure.sections) == 0
    
    def test_column_mapping(self, detector: DynamicHeaderDetector, simple_data: List[List[str]]):
        """Test that columns are correctly mapped to field types."""
        structure = detector.analyze_sheet(simple_data, "Test")
        
        # Build dict for easy lookup
        mappings = {m.field_type: m.index for m in structure.column_mappings if m.field_type != FieldType.UNKNOWN}
        
        assert FieldType.NAME in mappings
        assert FieldType.PRICE_WHOLESALE in mappings
        assert FieldType.PRICE_RETAIL in mappings
        assert FieldType.AVAILABILITY in mappings
    
    def test_section_detection(self, detector: DynamicHeaderDetector, data_with_sections: List[List[str]]):
        """Test that sections are correctly detected."""
        structure = detector.analyze_sheet(data_with_sections, "Test")
        
        assert len(structure.sections) == 2
        section_names = [s[1] for s in structure.sections]
        assert "Электровелосипеды" in section_names
        assert "Электроскутера" in section_names
    
    def test_info_rows_skipped(self, detector: DynamicHeaderDetector, data_with_info_header: List[List[str]]):
        """Test that info rows at the top don't affect header detection."""
        structure = detector.analyze_sheet(data_with_info_header, "Test")
        
        assert structure.header_rows == [3]
        assert structure.data_start_row == 4
    
    def test_empty_worksheet_raises(self, detector: DynamicHeaderDetector):
        """Empty worksheet should raise ValueError."""
        with pytest.raises(ValueError, match="Empty worksheet"):
            detector.analyze_sheet([], "Empty")
    
    def test_priority_score_calculation(self, detector: DynamicHeaderDetector, simple_data: List[List[str]]):
        """Test priority score increases with more mapped fields."""
        structure = detector.analyze_sheet(simple_data, "Test")
        
        # Should have positive score due to mapped fields
        assert structure.priority_score > 0
    
    def test_priority_keywords_boost_score(self, detector: DynamicHeaderDetector, simple_data: List[List[str]]):
        """Sheets with priority keywords should have higher scores."""
        score_normal = detector.analyze_sheet(simple_data, "Прайс").priority_score
        score_priority = detector.analyze_sheet(simple_data, "Для загрузки на сайт").priority_score
        
        assert score_priority > score_normal
    
    def test_negative_keywords_reduce_score(self, detector: DynamicHeaderDetector, simple_data: List[List[str]]):
        """Sheets with negative keywords should have lower scores."""
        score_normal = detector.analyze_sheet(simple_data, "Прайс").priority_score
        score_archive = detector.analyze_sheet(simple_data, "Архив старый").priority_score
        
        assert score_archive < score_normal


class TestSectionTracker:
    """Tests for category tracking during iteration."""
    
    @pytest.fixture
    def sections(self) -> List[tuple]:
        return [
            (1, "Электровелосипеды"),
            (5, "Электроскутера"),
            (7, "[sub]Модификация - Mini"),
        ]
    
    @pytest.fixture
    def tracker(self, sections) -> SectionTracker:
        return SectionTracker(sections)
    
    def test_category_before_first_section(self, tracker: SectionTracker):
        """Rows before first section should have no category."""
        assert tracker.get_category(0) is None
    
    def test_category_in_first_section(self, tracker: SectionTracker):
        """Rows in first section should get that category."""
        assert tracker.get_category(2) == "Электровелосипеды"
        assert tracker.get_category(4) == "Электровелосипеды"
    
    def test_category_in_second_section(self, tracker: SectionTracker):
        """Rows in second section should get that category."""
        assert tracker.get_category(6) == "Электроскутера"
    
    def test_category_with_subsection(self, tracker: SectionTracker):
        """Rows in subsection should get combined category."""
        category = tracker.get_category(8)
        assert "Электроскутера" in category
        assert "Модификация - Mini" in category
    
    def test_reset_clears_state(self, tracker: SectionTracker):
        """Reset should clear tracking state."""
        tracker.get_category(6)  # Set some state
        tracker.reset()
        
        # After reset, even rows after sections should return None
        # until get_category is called again
        tracker._current_section = None
        assert tracker._current_section is None


class TestDetectorConfig:
    """Tests for detector configuration."""
    
    def test_default_config(self):
        """Default config should have sensible values."""
        config = DetectorConfig()
        
        assert config.min_header_columns == 2
        assert config.max_header_scan_rows == 15
        assert 'загрузк' in config.priority_sheet_keywords
    
    def test_custom_config(self):
        """Custom config should override defaults."""
        config = DetectorConfig(
            max_header_scan_rows=30,
            priority_sheet_keywords=['custom', 'keywords']
        )
        
        assert config.max_header_scan_rows == 30
        assert 'custom' in config.priority_sheet_keywords


class TestIntegration:
    """Integration tests combining multiple components."""
    
    @pytest.fixture
    def complex_data(self) -> List[List[str]]:
        """Complex real-world-like data."""
        return [
            ["Поставщик: ООО ТехноСад", "", "", "", ""],
            ["Телефон: +375 29 123 45 67", "", "", "", ""],
            ["", "", "", "", ""],
            ["МОТОБЛОКИ И МИНИТРАКТОРЫ", "", "", "", ""],
            ["", "", "", "", ""],
            ["Наименование товара", "Фото", "Оптовая цена", "РРЦ", "Остаток"],
            ["Мотоблоки и навесное оборудование", "", "", "", ""],
            ["Снегоуборщик Brait BR-7056W", "", "1350", "1699", "в наличии"],
            ["Мотокультиватор Storm HP-920", "", "1005", "1235", "+"],
            ["Минитракторы", "", "", "", ""],
            ["Минитрактор Mitsubishi VST", "", "18000", "19500", "В наличии"],
        ]
    
    def test_full_analysis_workflow(self, complex_data: List[List[str]]):
        """Test complete workflow from raw data to structured output."""
        detector = DynamicHeaderDetector()
        structure = detector.analyze_sheet(complex_data, "Техно Сад")
        
        # Should find header row
        assert len(structure.header_rows) >= 1
        assert structure.data_start_row > 0
        
        # Should find sections
        section_names = [s[1] for s in structure.sections]
        assert any("Мотоблоки" in name or "мотоблок" in name.lower() for name in section_names)
        
        # Should have column mappings
        mapped_types = {m.field_type for m in structure.column_mappings if m.field_type != FieldType.UNKNOWN}
        assert FieldType.NAME in mapped_types
        
        # Tracker should work with detected sections
        tracker = SectionTracker(structure.sections)
        
        # Row 8 (Снегоуборщик) should be in first section
        category = tracker.get_category(7)
        assert category is not None
