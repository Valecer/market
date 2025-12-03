"""
Unit Tests for Prompt Templates
================================

Tests for LLM prompt template construction and formatting.
"""

import pytest

from src.rag.prompt_templates import (
    MATCH_PROMPT,
    BATCH_MATCH_PROMPT,
    NO_MATCH_PROMPT,
    format_candidates_text,
    format_item_for_prompt,
)


class TestFormatCandidatesText:
    """Tests for format_candidates_text function."""

    def test_format_single_candidate(self):
        """Test formatting a single candidate."""
        candidates = [
            {
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Energizer AA Battery 24-Pack",
                "similarity": 0.95,
                "characteristics": {"brand": "Energizer", "quantity": "24"},
            }
        ]

        result = format_candidates_text(candidates)

        assert "1. Product ID: 550e8400-e29b-41d4-a716-446655440000" in result
        assert "Name: Energizer AA Battery 24-Pack" in result
        assert "Similarity Score: 0.950" in result
        assert "brand: Energizer" in result
        assert "quantity: 24" in result

    def test_format_multiple_candidates(self):
        """Test formatting multiple candidates."""
        candidates = [
            {
                "product_id": "id-1",
                "name": "Product A",
                "similarity": 0.9,
                "characteristics": {},
            },
            {
                "product_id": "id-2",
                "name": "Product B",
                "similarity": 0.8,
                "characteristics": {"type": "basic"},
            },
            {
                "product_id": "id-3",
                "name": "Product C",
                "similarity": 0.7,
                "characteristics": {},
            },
        ]

        result = format_candidates_text(candidates)

        assert "1. Product ID: id-1" in result
        assert "2. Product ID: id-2" in result
        assert "3. Product ID: id-3" in result
        assert "Product A" in result
        assert "Product B" in result
        assert "Product C" in result

    def test_format_empty_candidates(self):
        """Test formatting empty candidate list."""
        result = format_candidates_text([])

        assert result == "No candidates available."

    def test_format_candidate_without_characteristics(self):
        """Test formatting candidate with no characteristics."""
        candidates = [
            {
                "product_id": "test-id",
                "name": "Simple Product",
                "similarity": 0.85,
                "characteristics": {},
            }
        ]

        result = format_candidates_text(candidates)

        assert "Characteristics: none" in result

    def test_format_candidate_missing_fields(self):
        """Test formatting candidate with missing fields uses defaults."""
        candidates = [
            {
                "name": "Partial Product",
                "similarity": 0.75,
            }
        ]

        result = format_candidates_text(candidates)

        assert "Product ID: unknown" in result
        assert "Partial Product" in result

    def test_format_similarity_precision(self):
        """Test similarity score is formatted to 3 decimal places."""
        candidates = [
            {
                "product_id": "id",
                "name": "Test",
                "similarity": 0.87654321,
                "characteristics": {},
            }
        ]

        result = format_candidates_text(candidates)

        assert "0.877" in result  # Rounded to 3 decimals


class TestFormatItemForPrompt:
    """Tests for format_item_for_prompt function."""

    def test_format_full_item(self):
        """Test formatting item with all fields."""
        result = format_item_for_prompt(
            name="Energizer AA Battery 24-Pack",
            description="Long-lasting alkaline batteries",
            sku="EN-AA-24",
            category="Batteries",
            brand="Energizer",
            characteristics={"voltage": "1.5V", "type": "Alkaline"},
        )

        assert result["item_name"] == "Energizer AA Battery 24-Pack"
        assert result["item_description"] == "Long-lasting alkaline batteries"
        assert result["item_sku"] == "EN-AA-24"
        assert result["item_category"] == "Batteries"
        assert result["item_brand"] == "Energizer"
        assert "voltage: 1.5V" in result["item_characteristics"]
        assert "type: Alkaline" in result["item_characteristics"]

    def test_format_minimal_item(self):
        """Test formatting item with only required name."""
        result = format_item_for_prompt(name="Simple Item")

        assert result["item_name"] == "Simple Item"
        assert result["item_description"] == "Not provided"
        assert result["item_sku"] == "Not provided"
        assert result["item_category"] == "Not provided"
        assert result["item_brand"] == "Not provided"
        assert result["item_characteristics"] == "none"

    def test_format_item_none_characteristics(self):
        """Test formatting with None characteristics."""
        result = format_item_for_prompt(
            name="Test",
            characteristics=None,
        )

        assert result["item_characteristics"] == "none"

    def test_format_item_empty_characteristics(self):
        """Test formatting with empty characteristics dict."""
        result = format_item_for_prompt(
            name="Test",
            characteristics={},
        )

        assert result["item_characteristics"] == "none"


class TestMatchPrompt:
    """Tests for MATCH_PROMPT template."""

    def test_prompt_format_messages(self):
        """Test prompt can be formatted with all variables."""
        variables = {
            "item_name": "Test Product",
            "item_description": "A test product",
            "item_sku": "TEST-001",
            "item_category": "Test Category",
            "item_brand": "TestBrand",
            "item_characteristics": "color: red, size: large",
            "candidates_text": "1. Product ID: xxx\n   Name: Candidate",
            "top_k": "5",
        }

        # Should not raise
        messages = MATCH_PROMPT.format_messages(**variables)

        assert len(messages) == 2  # System + Human
        assert messages[0].type == "system"
        assert messages[1].type == "human"

    def test_prompt_contains_instructions(self):
        """Test prompt includes key instructions."""
        variables = format_item_for_prompt(name="Test")
        variables["candidates_text"] = "No candidates"
        variables["top_k"] = "5"

        messages = MATCH_PROMPT.format_messages(**variables)
        human_content = messages[1].content

        # Check for key instructions
        assert "JSON" in human_content
        assert "confidence" in human_content.lower()
        assert "reasoning" in human_content.lower()
        assert "product_id" in human_content.lower()

    def test_prompt_system_message_content(self):
        """Test system message has correct guidance."""
        variables = format_item_for_prompt(name="Test")
        variables["candidates_text"] = "Test"
        variables["top_k"] = "5"

        messages = MATCH_PROMPT.format_messages(**variables)
        system_content = messages[0].content

        assert "product matching expert" in system_content.lower()
        assert "JSON" in system_content
        assert "confidence" in system_content.lower()


class TestBatchMatchPrompt:
    """Tests for BATCH_MATCH_PROMPT template."""

    def test_batch_prompt_format(self):
        """Test batch prompt can be formatted."""
        variables = {
            "items_text": "Item 1: Test\nItem 2: Another",
            "candidates_text": "Candidate list here",
        }

        messages = BATCH_MATCH_PROMPT.format_messages(**variables)

        assert len(messages) == 2
        human_content = messages[1].content
        assert "Item 1" in human_content
        assert "Item 2" in human_content


class TestNoMatchPrompt:
    """Tests for NO_MATCH_PROMPT template."""

    def test_no_match_prompt_format(self):
        """Test no-match explanation prompt."""
        result = NO_MATCH_PROMPT.format(
            item_name="Test Product",
            candidate_count=5,
            best_similarity=0.45,
        )

        assert "Test Product" in result
        assert "5" in result
        assert "0.45" in result


class TestPromptIntegration:
    """Integration tests for prompt template workflow."""

    def test_full_prompt_workflow(self):
        """Test complete workflow of building and formatting prompt."""
        # Step 1: Format item
        item_vars = format_item_for_prompt(
            name="Duracell AA Battery 12-Pack",
            description="Premium alkaline batteries",
            sku="DUR-AA-12",
            category="Batteries",
            brand="Duracell",
            characteristics={"voltage": "1.5V", "count": "12"},
        )

        # Step 2: Format candidates
        candidates = [
            {
                "product_id": "uuid-1",
                "name": "Duracell AA Batteries 12-Pack",
                "similarity": 0.98,
                "characteristics": {"brand": "Duracell"},
            },
            {
                "product_id": "uuid-2",
                "name": "Energizer AA 12-Pack",
                "similarity": 0.85,
                "characteristics": {"brand": "Energizer"},
            },
        ]
        item_vars["candidates_text"] = format_candidates_text(candidates)
        item_vars["top_k"] = "5"

        # Step 3: Build prompt
        messages = MATCH_PROMPT.format_messages(**item_vars)

        # Verify structure
        assert len(messages) == 2

        # Verify content
        human_msg = messages[1].content
        assert "Duracell AA Battery 12-Pack" in human_msg
        assert "Premium alkaline batteries" in human_msg
        assert "DUR-AA-12" in human_msg
        assert "uuid-1" in human_msg
        assert "uuid-2" in human_msg
        assert "0.98" in human_msg or "0.980" in human_msg

    def test_prompt_with_unicode(self):
        """Test prompt handles unicode characters."""
        item_vars = format_item_for_prompt(
            name="Батарейка AA Alkaline",  # Russian
            description="Щелочная батарейка типа AA",
            brand="Duracell",
            characteristics={"тип": "щелочная"},  # Russian keys
        )
        item_vars["candidates_text"] = "No candidates"
        item_vars["top_k"] = "5"

        # Should not raise
        messages = MATCH_PROMPT.format_messages(**item_vars)
        human_content = messages[1].content

        assert "Батарейка" in human_content
        assert "тип" in human_content

    def test_prompt_with_special_characters(self):
        """Test prompt handles special characters."""
        item_vars = format_item_for_prompt(
            name='Product "Special" (Version 2.0)',
            description="Contains <special> & 'chars'",
            characteristics={"size": "10\" x 20\""},
        )
        item_vars["candidates_text"] = "Test"
        item_vars["top_k"] = "5"

        # Should not raise
        messages = MATCH_PROMPT.format_messages(**item_vars)
        human_content = messages[1].content

        assert '"Special"' in human_content


