"""Agent runtime interfaces and LLM provider protocol abstractions.

Owner: C2
"""

from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Type,
    TypeVar,
)

from contracts.models import Persona, RequestEnvelope, RouteDecision, RuntimeResult
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    """Protocol decoupling orchestrator from any LLM vendor SDK (OpenAI, Anthropic, Gemini, etc.)."""

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """Execute a text completion prompt."""
        ...

    async def structured(
        self,
        prompt: str,
        schema: Type[T] | Dict[str, Any],
        system: str = "",
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Any:
        """Execute structured JSON completion adhering to a Pydantic model or schema."""
        ...


class AgentRuntime(Protocol):
    """Protocol for executing an agent turn using a selected Persona and RouteDecision."""

    async def execute(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        **kwargs: Any,
    ) -> RuntimeResult:
        """Run the persona loop and produce structured RuntimeResult."""
        ...

    def stream(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream response tokens as an asynchronous iterator."""
        ...


class LLMProviderRegistry:
    """Registry for pluggable LLM provider backends."""

    _registry: Dict[str, Callable[..., LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., LLMProvider]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> LLMProvider:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"LLM Provider '{name}' not found. Registered providers: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        from personas_runtime.mock_llm import MockLLMProvider

        cls.register("mock", lambda **kwargs: MockLLMProvider(**kwargs))
        cls.register("unset", lambda **kwargs: MockLLMProvider(**kwargs))
        cls.register("default", lambda **kwargs: MockLLMProvider(**kwargs))


class RuntimeRegistry:
    """Registry for pluggable AgentRuntime implementations."""

    _registry: Dict[str, Callable[..., AgentRuntime]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., AgentRuntime]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> AgentRuntime:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"Agent Runtime '{name}' not found. Registered runtimes: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        from personas_runtime.echo_runtime import EchoRuntime, ScriptedRuntime

        cls.register("echo", lambda **kwargs: EchoRuntime())
        cls.register("scripted", lambda **kwargs: ScriptedRuntime())
        cls.register("default", lambda **kwargs: EchoRuntime())
