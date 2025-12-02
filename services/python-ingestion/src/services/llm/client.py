"""LLM Client abstraction for local model integration.

Supports multiple backends:
- Ollama (primary, recommended for local deployment)
- Direct HTTP API (for custom endpoints)

Designed for:
- Header detection in spreadsheets
- Product classification/categorization
- Similar product matching

Example:
    client = OllamaClient(model="llama3.2")
    result = await client.complete("Classify this product: ...")
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, TypeVar, Generic
from enum import Enum
import structlog
import httpx

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class LLMBackend(str, Enum):
    """Supported LLM backends."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    MOCK = "mock"  # For testing


@dataclass
class LLMConfig:
    """Configuration for LLM client."""
    backend: LLMBackend = LLMBackend.OLLAMA
    model: str = "llama3.2"  # Default to smaller, faster model
    base_url: str = "http://localhost:11434"
    api_key: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 3
    temperature: float = 0.1  # Low temperature for consistent results
    max_tokens: int = 2048


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Optional[Dict[str, Any]] = None
    
    @property
    def tokens_used(self) -> int:
        """Total tokens used in this response."""
        return self.usage.get("total_tokens", 0)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._log = logger.bind(
            component="LLMClient",
            backend=self.config.backend.value,
            model=self.config.model
        )
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate a completion for the given prompt.
        
        Args:
            prompt: User prompt to complete
            system_prompt: Optional system prompt for context
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a JSON completion.
        
        Args:
            prompt: User prompt expecting JSON output
            system_prompt: Optional system prompt
            schema: Optional JSON schema for validation
            
        Returns:
            Parsed JSON response
        """
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the LLM backend is available."""
        pass


class OllamaClient(LLMClient):
    """Ollama-based LLM client.
    
    Ollama provides a simple way to run local LLMs. This client
    communicates with the Ollama API (default: http://localhost:11434).
    
    Recommended models for this project:
    - llama3.2 (8B) - Fast, good for classification
    - llama3.2:1b - Fastest, good for simple tasks
    - mistral (7B) - Good balance
    - qwen2.5:7b - Excellent for Russian text
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            
            # Check if our model is available
            model_base = self.config.model.split(":")[0]
            available = any(
                m.startswith(model_base) for m in models
            )
            
            if not available:
                self._log.warning(
                    "model_not_available",
                    required_model=self.config.model,
                    available_models=models,
                )
            
            return available
            
        except Exception as e:
            self._log.debug("ollama_not_available", error=str(e))
            return False
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate completion using Ollama API."""
        client = await self._get_client()
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(
                    "/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                
                data = response.json()
                
                return LLMResponse(
                    content=data.get("response", ""),
                    model=data.get("model", self.config.model),
                    usage={
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": (
                            data.get("prompt_eval_count", 0) +
                            data.get("eval_count", 0)
                        ),
                    },
                    raw_response=data,
                )
                
            except httpx.HTTPStatusError as e:
                self._log.warning(
                    "ollama_request_failed",
                    attempt=attempt + 1,
                    status=e.response.status_code,
                    error=str(e),
                )
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(1 * (attempt + 1))
                
            except Exception as e:
                self._log.error(
                    "ollama_unexpected_error",
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(1 * (attempt + 1))
        
        raise RuntimeError("Failed to complete after retries")
    
    async def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate JSON completion using Ollama.
        
        Uses format="json" to ensure valid JSON output.
        """
        client = await self._get_client()
        
        # Enhance prompt to request JSON
        json_prompt = prompt
        if not any(word in prompt.lower() for word in ["json", "формат"]):
            json_prompt = f"{prompt}\n\nОтветь только в формате JSON."
        
        enhanced_system = system_prompt or ""
        if schema:
            schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
            enhanced_system += f"\n\nОжидаемая структура JSON:\n{schema_str}"
        
        payload = {
            "model": self.config.model,
            "prompt": json_prompt,
            "stream": False,
            "format": "json",  # Force JSON output
            "options": {
                "temperature": 0.0,  # Deterministic for JSON
                "num_predict": self.config.max_tokens,
            }
        }
        
        if enhanced_system:
            payload["system"] = enhanced_system
        
        try:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            
            data = response.json()
            content = data.get("response", "{}")
            
            # Parse JSON response
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError as e:
                self._log.warning(
                    "json_parse_failed",
                    content=content[:200],
                    error=str(e),
                )
                # Try to extract JSON from response
                return self._extract_json(content)
                
        except Exception as e:
            self._log.error("complete_json_failed", error=str(e))
            raise
    
    def _extract_json(self, content: str) -> Dict[str, Any]:
        """Try to extract JSON from content that might have extra text."""
        import re
        
        # Try to find JSON object
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON array
        array_match = re.search(r'\[[^\[\]]*\]', content, re.DOTALL)
        if array_match:
            try:
                return {"items": json.loads(array_match.group())}
            except json.JSONDecodeError:
                pass
        
        return {}


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""
    
    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        responses: Optional[Dict[str, str]] = None,
    ):
        super().__init__(config or LLMConfig(backend=LLMBackend.MOCK))
        self.responses = responses or {}
        self.calls: List[Dict[str, Any]] = []
    
    async def is_available(self) -> bool:
        return True
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        self.calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        
        # Find matching response
        for key, response in self.responses.items():
            if key.lower() in prompt.lower():
                return LLMResponse(
                    content=response,
                    model="mock",
                    usage={"total_tokens": 100},
                )
        
        return LLMResponse(
            content="Mock response",
            model="mock",
            usage={"total_tokens": 50},
        )
    
    async def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "schema": schema,
            "json": True,
        })
        
        return {"mock": True, "prompt": prompt[:50]}


# Global client instance
_global_client: Optional[LLMClient] = None


def get_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """Get or create global LLM client.
    
    Args:
        config: Optional configuration (uses defaults if not provided)
        
    Returns:
        LLMClient instance
    """
    global _global_client
    
    if _global_client is None or config is not None:
        cfg = config or LLMConfig()
        
        if cfg.backend == LLMBackend.OLLAMA:
            _global_client = OllamaClient(cfg)
        elif cfg.backend == LLMBackend.MOCK:
            _global_client = MockLLMClient(cfg)
        else:
            # Default to Ollama
            _global_client = OllamaClient(cfg)
    
    return _global_client


async def reset_llm_client() -> None:
    """Reset the global LLM client (for testing)."""
    global _global_client
    
    if _global_client:
        if hasattr(_global_client, "close"):
            await _global_client.close()
        _global_client = None

