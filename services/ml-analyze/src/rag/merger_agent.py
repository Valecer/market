"""
Merger Agent
=============

LLM-based product matching using RAG (Retrieval-Augmented Generation).

Pipeline:
1. Generate embedding for supplier item
2. Vector search to find Top-K candidates
3. Construct prompt with item + candidates
4. LLM call for structured matching
5. Parse JSON response with confidence scores

Follows:
- Single Responsibility: Only handles LLM-based matching logic
- Dependency Inversion: Depends on VectorService abstraction
- Error Isolation: Graceful handling of LLM failures
- SOLID: Clear contracts between components
"""

import json
import re
from typing import Any
from uuid import UUID

from langchain_ollama import ChatOllama
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings, get_settings
from src.rag.prompt_templates import (
    MATCH_PROMPT,
    format_candidates_text,
    format_item_for_prompt,
)
from src.rag.vector_service import VectorService
from src.schemas.domain import MatchResult, SimilarityResult
from src.utils.errors import LLMError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMMatchResponse:
    """
    Parsed response from LLM matching.

    Contains structured match results with validation applied.
    """

    def __init__(
        self,
        matches: list[MatchResult],
        raw_response: str,
        parse_success: bool = True,
        error_message: str | None = None,
    ) -> None:
        self.matches = matches
        self.raw_response = raw_response
        self.parse_success = parse_success
        self.error_message = error_message

    @property
    def has_matches(self) -> bool:
        """Check if any matches were found."""
        return len(self.matches) > 0

    @property
    def best_match(self) -> MatchResult | None:
        """Get the highest confidence match."""
        if not self.matches:
            return None
        return max(self.matches, key=lambda m: m.confidence)


class MergerAgent:
    """
    LLM-based product matching agent.

    Uses RAG pipeline:
    1. Vector search for candidate matches
    2. LLM reasoning for confirmation
    3. Confidence scoring

    Architecture:
        MergerAgent → VectorService → pgvector (similarity)
                   → ChatOllama → Ollama API (reasoning)

    Usage:
        async with get_session() as session:
            agent = MergerAgent(session)
            results = await agent.find_matches(item_data)

            for match in results:
                if match.confidence > 0.9:
                    # Auto-match
                elif match.confidence >= 0.7:
                    # Add to review queue
                else:
                    # Log and skip
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        vector_service: VectorService | None = None,
    ) -> None:
        """
        Initialize MergerAgent.

        Args:
            session: SQLAlchemy async session
            settings: Application settings (uses default if not provided)
            vector_service: Optional VectorService instance
        """
        self._session = session
        self._settings = settings or get_settings()

        # Initialize VectorService for similarity search
        self._vector_service = vector_service or VectorService(session, settings)

        # Initialize ChatOllama for LLM reasoning
        self._llm = ChatOllama(
            model=self._settings.ollama_llm_model,
            base_url=self._settings.ollama_base_url,
            temperature=0.1,  # Low temperature for deterministic outputs
            format="json",  # Request JSON output
        )

        # Confidence thresholds from settings
        self._auto_threshold = self._settings.match_confidence_auto_threshold
        self._review_threshold = self._settings.match_confidence_review_threshold

        logger.debug(
            "MergerAgent initialized",
            llm_model=self._settings.ollama_llm_model,
            auto_threshold=self._auto_threshold,
            review_threshold=self._review_threshold,
        )

    async def find_matches(
        self,
        item_name: str,
        item_description: str | None = None,
        item_sku: str | None = None,
        item_category: str | None = None,
        item_brand: str | None = None,
        item_characteristics: dict[str, Any] | None = None,
        supplier_item_id: UUID | None = None,
        top_k: int = 5,
    ) -> list[MatchResult]:
        """
        Find matching products for a supplier item.

        Pipeline:
        1. Generate embedding for item text
        2. Search for Top-K similar items
        3. Query LLM with item + candidates
        4. Parse and validate JSON response
        5. Return MatchResult objects

        Args:
            item_name: Supplier item name
            item_description: Optional description
            item_sku: Optional SKU
            item_category: Optional category
            item_brand: Optional brand
            item_characteristics: Optional characteristics dict
            supplier_item_id: Optional ID to exclude from similarity search
            top_k: Number of candidates to retrieve

        Returns:
            List of MatchResult objects with confidence scores

        Raises:
            LLMError: If LLM call fails after retries
        """
        logger.info(
            "Finding matches for item",
            item_name=item_name[:50],
            top_k=top_k,
        )

        try:
            # Step 1: Create text representation for embedding
            item_text = self._build_item_text(
                name=item_name,
                description=item_description,
                brand=item_brand,
                category=item_category,
                characteristics=item_characteristics,
            )

            # Step 2: Vector search for candidates
            candidates = await self._vector_service.similarity_search_text(
                query_text=item_text,
                top_k=top_k,
                exclude_item_id=supplier_item_id,
            )

            if not candidates:
                logger.info("No candidates found via vector search", item_name=item_name[:50])
                return []

            logger.debug(
                "Candidates found",
                count=len(candidates),
                top_similarity=candidates[0].similarity if candidates else 0.0,
            )

            # Step 3: Prepare prompt inputs
            prompt_vars = format_item_for_prompt(
                name=item_name,
                description=item_description,
                sku=item_sku,
                category=item_category,
                brand=item_brand,
                characteristics=item_characteristics,
            )

            candidates_data = [
                {
                    "product_id": str(c.product_id) if c.product_id else str(c.supplier_item_id),
                    "name": c.name,
                    "similarity": c.similarity,
                    "characteristics": c.characteristics,
                }
                for c in candidates
            ]

            prompt_vars["candidates_text"] = format_candidates_text(candidates_data)
            prompt_vars["top_k"] = str(top_k)

            # Step 4: Call LLM
            llm_response = await self._call_llm(prompt_vars)

            # Step 5: Parse response
            parsed = self._parse_llm_response(llm_response, candidates)

            if not parsed.parse_success:
                logger.warning(
                    "LLM response parse failed",
                    error=parsed.error_message,
                    raw_response=parsed.raw_response[:200] if parsed.raw_response else None,
                )
                return []

            logger.info(
                "Matches found",
                count=len(parsed.matches),
                best_confidence=parsed.best_match.confidence if parsed.best_match else 0.0,
            )

            return parsed.matches

        except LLMError:
            raise
        except Exception as e:
            logger.exception("Unexpected error in find_matches", error=str(e))
            raise LLMError(
                message="Failed to find matches",
                details={"error": str(e), "item_name": item_name[:50]},
            ) from e

    async def _call_llm(self, prompt_vars: dict[str, str]) -> str:
        """
        Call LLM with prompt and return response.

        Args:
            prompt_vars: Variables for prompt template

        Returns:
            LLM response text

        Raises:
            LLMError: If LLM call fails
        """
        try:
            logger.debug("Calling LLM for matching")

            # Format prompt
            messages = MATCH_PROMPT.format_messages(**prompt_vars)

            # Invoke LLM (async)
            response = await self._llm.ainvoke(messages)

            # Extract content
            content = response.content if hasattr(response, "content") else str(response)

            logger.debug(
                "LLM response received",
                response_length=len(content) if content else 0,
            )

            return content

        except Exception as e:
            logger.error("LLM call failed", error=str(e))
            raise LLMError(
                message="LLM call failed",
                details={"error": str(e)},
            ) from e

    def _parse_llm_response(
        self,
        response: str,
        candidates: list[SimilarityResult],
    ) -> LLMMatchResponse:
        """
        Parse LLM JSON response into MatchResult objects.

        Handles:
        - Valid JSON array
        - Empty array (no matches)
        - Markdown code blocks (extracts JSON)
        - Invalid JSON (graceful failure)

        Args:
            response: Raw LLM response text
            candidates: Original candidates (for enrichment)

        Returns:
            LLMMatchResponse with parsed matches or error info
        """
        if not response or not response.strip():
            return LLMMatchResponse(
                matches=[],
                raw_response=response,
                parse_success=False,
                error_message="Empty LLM response",
            )

        try:
            # Clean response - extract JSON from potential markdown
            json_text = self._extract_json_from_response(response)

            # Parse JSON
            data = json.loads(json_text)

            # Handle both array and object responses
            if isinstance(data, list):
                matches_data = data
            elif isinstance(data, dict):
                # Some LLMs wrap in an object
                matches_data = data.get("matches", data.get("results", [data]))
            else:
                return LLMMatchResponse(
                    matches=[],
                    raw_response=response,
                    parse_success=False,
                    error_message=f"Unexpected JSON type: {type(data).__name__}",
                )

            # Convert to MatchResult objects
            matches = []
            candidate_map = {
                str(c.product_id) if c.product_id else str(c.supplier_item_id): c
                for c in candidates
            }

            for item in matches_data:
                if not isinstance(item, dict):
                    continue

                product_id_str = item.get("product_id", "")
                confidence = item.get("confidence", 0.0)
                reasoning = item.get("reasoning", "")

                # Skip invalid entries
                if not product_id_str:
                    continue

                # Validate confidence
                try:
                    confidence = float(confidence)
                    confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
                except (ValueError, TypeError):
                    confidence = 0.0

                # Get similarity score from original candidate
                similarity_score = 0.0
                product_name = "Unknown"
                if product_id_str in candidate_map:
                    similarity_score = candidate_map[product_id_str].similarity
                    product_name = candidate_map[product_id_str].name

                # Parse UUID
                try:
                    product_id = UUID(product_id_str)
                except ValueError:
                    logger.warning("Invalid product_id UUID", product_id=product_id_str)
                    continue

                matches.append(
                    MatchResult(
                        product_id=product_id,
                        product_name=product_name,
                        confidence=confidence,
                        reasoning=reasoning or "Match confirmed by LLM",
                        similarity_score=similarity_score,
                    )
                )

            return LLMMatchResponse(
                matches=matches,
                raw_response=response,
                parse_success=True,
            )

        except json.JSONDecodeError as e:
            return LLMMatchResponse(
                matches=[],
                raw_response=response,
                parse_success=False,
                error_message=f"JSON decode error: {e.msg}",
            )
        except Exception as e:
            return LLMMatchResponse(
                matches=[],
                raw_response=response,
                parse_success=False,
                error_message=f"Parse error: {str(e)}",
            )

    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from LLM response.

        Handles markdown code blocks and other wrapping.

        Args:
            response: Raw response text

        Returns:
            Cleaned JSON text
        """
        text = response.strip()

        # Remove markdown code blocks
        if text.startswith("```"):
            # Extract content between code blocks
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()
            else:
                # Remove just the backticks
                text = re.sub(r"```(?:json)?", "", text).strip()

        return text

    def _build_item_text(
        self,
        name: str,
        description: str | None = None,
        brand: str | None = None,
        category: str | None = None,
        characteristics: dict[str, Any] | None = None,
    ) -> str:
        """
        Build text representation for embedding.

        Args:
            name: Item name
            description: Optional description
            brand: Optional brand
            category: Optional category
            characteristics: Optional characteristics

        Returns:
            Combined text for embedding
        """
        parts = [name]

        if brand:
            parts.append(brand)
        if category:
            parts.append(category)
        if description:
            parts.append(description)
        if characteristics:
            char_str = " ".join(f"{k}: {v}" for k, v in characteristics.items())
            parts.append(char_str)

        return " ".join(parts)

    def classify_match(self, match: MatchResult) -> str:
        """
        Classify match based on confidence threshold.

        Args:
            match: MatchResult to classify

        Returns:
            Classification: 'auto', 'review', or 'reject'
        """
        if match.confidence >= self._auto_threshold:
            return "auto"
        elif match.confidence >= self._review_threshold:
            return "review"
        else:
            return "reject"

    def filter_by_classification(
        self,
        matches: list[MatchResult],
        classification: str,
    ) -> list[MatchResult]:
        """
        Filter matches by classification.

        Args:
            matches: List of matches to filter
            classification: 'auto', 'review', or 'reject'

        Returns:
            Filtered list of matches
        """
        return [m for m in matches if self.classify_match(m) == classification]


