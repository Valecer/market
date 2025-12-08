"""
LLM Callbacks for Semantic ETL Pipeline
========================================

Streaming and monitoring callbacks for LangChain LLM calls.
Allows real-time observation of LLM output generation.

Usage:
    from src.services.smart_parser.llm_callbacks import StreamingCallback
    
    callback = StreamingCallback()
    llm = ChatOllama(..., callbacks=[callback])
"""

import sys
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from src.utils.logger import get_logger

logger = get_logger(__name__)


class StreamingCallback(BaseCallbackHandler):
    """
    Callback handler that streams LLM output tokens to stdout.
    
    Useful for debugging and monitoring LLM generation in real-time.
    """
    
    def __init__(self, print_to_stdout: bool = True, collect_tokens: bool = False):
        """
        Initialize streaming callback.
        
        Args:
            print_to_stdout: Print tokens to stdout as they arrive
            collect_tokens: Collect all tokens for later inspection
        """
        self.print_to_stdout = print_to_stdout
        self.collect_tokens = collect_tokens
        self.tokens: list[str] = []
        self._current_chunk_id: int | None = None
    
    def set_chunk_id(self, chunk_id: int) -> None:
        """Set current chunk ID for context."""
        self._current_chunk_id = chunk_id
    
    def on_llm_start(
        self, 
        serialized: dict[str, Any], 
        prompts: list[str], 
        **kwargs: Any
    ) -> None:
        """Called when LLM starts processing."""
        chunk_info = f" (chunk {self._current_chunk_id})" if self._current_chunk_id is not None else ""
        
        if self.print_to_stdout:
            print(f"\n{'='*60}")
            print(f"🤖 LLM Started{chunk_info}")
            print(f"{'='*60}")
            print(f"Prompt length: {len(prompts[0]) if prompts else 0} chars")
            print(f"{'='*60}")
            print("Response: ", end="", flush=True)
        
        logger.debug(
            "llm_callback.start",
            chunk_id=self._current_chunk_id,
            prompt_length=len(prompts[0]) if prompts else 0,
        )
        
        self.tokens = []
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called when a new token is generated."""
        if self.print_to_stdout:
            # Print token without newline, flush immediately
            print(token, end="", flush=True)
        
        if self.collect_tokens:
            self.tokens.append(token)
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM finishes."""
        if self.print_to_stdout:
            print(f"\n{'='*60}")
            print(f"✅ LLM Finished")
            print(f"{'='*60}\n")
        
        logger.debug(
            "llm_callback.end",
            chunk_id=self._current_chunk_id,
            total_tokens=len(self.tokens),
        )
    
    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Called when LLM encounters an error."""
        if self.print_to_stdout:
            print(f"\n{'='*60}")
            print(f"❌ LLM Error: {error}")
            print(f"{'='*60}\n")
        
        logger.error(
            "llm_callback.error",
            chunk_id=self._current_chunk_id,
            error=str(error),
        )
    
    def get_collected_tokens(self) -> str:
        """Return all collected tokens as a single string."""
        return "".join(self.tokens)


class VerboseCallback(BaseCallbackHandler):
    """
    Verbose callback that logs all LLM interactions with full details.
    
    Useful for debugging prompt engineering and understanding LLM behavior.
    """
    
    def __init__(self, log_prompts: bool = True, log_responses: bool = True):
        """
        Initialize verbose callback.
        
        Args:
            log_prompts: Log full prompts sent to LLM
            log_responses: Log full responses from LLM
        """
        self.log_prompts = log_prompts
        self.log_responses = log_responses
        self._start_time: float | None = None
    
    def on_llm_start(
        self, 
        serialized: dict[str, Any], 
        prompts: list[str], 
        **kwargs: Any
    ) -> None:
        """Log prompt details when LLM starts."""
        import time
        self._start_time = time.time()
        
        if self.log_prompts and prompts:
            prompt = prompts[0]
            print(f"\n{'='*80}")
            print("📝 PROMPT SENT TO LLM")
            print(f"{'='*80}")
            print(prompt)
            print(f"{'='*80}\n")
            
            logger.info(
                "llm_verbose.prompt",
                prompt_length=len(prompt),
                prompt_preview=prompt[:500] + "..." if len(prompt) > 500 else prompt,
            )
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Log response details when LLM finishes."""
        import time
        duration = time.time() - self._start_time if self._start_time else 0
        
        if self.log_responses and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    text = gen.text
                    print(f"\n{'='*80}")
                    print(f"📤 LLM RESPONSE (took {duration:.2f}s)")
                    print(f"{'='*80}")
                    print(text)
                    print(f"{'='*80}\n")
                    
                    logger.info(
                        "llm_verbose.response",
                        duration_seconds=round(duration, 2),
                        response_length=len(text),
                        response_preview=text[:500] + "..." if len(text) > 500 else text,
                    )


class MetricsCallback(BaseCallbackHandler):
    """
    Callback that collects metrics about LLM usage.
    
    Tracks:
    - Request count
    - Total tokens generated
    - Total time spent
    - Average response time
    """
    
    def __init__(self):
        self.request_count: int = 0
        self.total_tokens: int = 0
        self.total_time: float = 0.0
        self._current_start: float | None = None
        self._current_tokens: int = 0
    
    def on_llm_start(
        self, 
        serialized: dict[str, Any], 
        prompts: list[str], 
        **kwargs: Any
    ) -> None:
        """Track request start."""
        import time
        self._current_start = time.time()
        self._current_tokens = 0
        self.request_count += 1
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Count tokens."""
        self._current_tokens += 1
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Track request completion."""
        import time
        if self._current_start:
            self.total_time += time.time() - self._current_start
        self.total_tokens += self._current_tokens
    
    def get_metrics(self) -> dict[str, Any]:
        """Get collected metrics."""
        return {
            "request_count": self.request_count,
            "total_tokens": self.total_tokens,
            "total_time_seconds": round(self.total_time, 2),
            "avg_time_per_request": round(self.total_time / self.request_count, 2) if self.request_count > 0 else 0,
            "avg_tokens_per_request": round(self.total_tokens / self.request_count, 2) if self.request_count > 0 else 0,
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.request_count = 0
        self.total_tokens = 0
        self.total_time = 0.0
