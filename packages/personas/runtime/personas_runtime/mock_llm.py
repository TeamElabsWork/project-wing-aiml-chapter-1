"""MockLLMProvider implementing LLMProvider protocol without external network calls or SDKs.

Owner: C2
"""

from typing import Any, Dict, Type, TypeVar

from contracts.models import LLMResponse, TokenUsage
from pydantic import BaseModel

from personas_runtime.base import LLMProviderRegistry

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider:
    """Mock LLM provider returning simulated responses for tests and day-1 runs."""

    def __init__(self, canned_response: str | None = None) -> None:
        self.canned_response = canned_response

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        # TODO (C2 Runtime Owner): Implement real vendor integrations
        # (Anthropic, OpenAI, LiteLLM) behind this protocol in separate adapters.
        if self.canned_response:
            text = self.canned_response
        else:
            text = f"[MockLLM Complete]: Processed prompt of length {len(prompt)} with system prompt '{system[:30]}'."

        prompt_tokens = (len(prompt) + len(system)) // 4
        completion_tokens = len(text) // 4
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated=True,
        )
        return LLMResponse(text=text, usage=usage)

    async def structured(
        self,
        prompt: str,
        schema: Type[T] | Dict[str, Any],
        system: str = "",
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResponse:
        # TODO (C2 Runtime Owner): Implement JSON schema enforcement / tool calling schemas.
        parsed: Any = None
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                parsed = schema()
            except Exception:
                pass
        if parsed is None:
            parsed = {"result": f"[MockLLM Structured]: Generated for schema {schema}"}

        prompt_tokens = (len(prompt) + len(system)) // 4
        completion_tokens = len(str(parsed)) // 4
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated=True,
        )
        return LLMResponse(parsed=parsed, usage=usage)


LLMProviderRegistry.register_defaults()
