"""MockLLMProvider implementing LLMProvider protocol without external network calls or SDKs.

Owner: C2
"""

from typing import Any, Dict, Type, TypeVar

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
    ) -> str:
        # TODO (C2 Runtime Owner): Implement real vendor integrations
        # (Anthropic, OpenAI, LiteLLM) behind this protocol in separate adapters.
        if self.canned_response:
            return self.canned_response
        return f"[MockLLM Complete]: Processed prompt of length {len(prompt)} with system prompt '{system[:30]}'."

    async def structured(
        self,
        prompt: str,
        schema: Type[T] | Dict[str, Any],
        system: str = "",
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Any:
        # TODO (C2 Runtime Owner): Implement JSON schema enforcement / tool calling schemas.
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                return schema()
            except Exception:
                pass
        return {"result": f"[MockLLM Structured]: Generated for schema {schema}"}


LLMProviderRegistry.register_defaults()
