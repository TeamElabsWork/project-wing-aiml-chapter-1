"""Router protocol and router registry.

Owner: B2
"""

from typing import Any, Callable, Dict, List, Protocol

from contracts.models import (
    MemoryNode,
    PolicyEvaluation,
    RequestEnvelope,
    RouteDecision,
    SessionState,
)


class Router(Protocol):
    """Protocol implemented by routing engines (LLM-based, heuristic, or hybrid)."""

    async def route(
        self,
        envelope: RequestEnvelope,
        session_state: SessionState,
        surface_policy: PolicyEvaluation,
        memory_context: List[MemoryNode],
    ) -> RouteDecision:
        """Analyze context and make a RouteDecision."""
        ...


class RouterRegistry:
    """Registry allowing router implementations to be registered and selected via config."""

    _registry: Dict[str, Callable[..., Router]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., Router]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> Router:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"Router '{name}' not found in registry. Registered routers: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def list_available(cls) -> List[str]:
        return list(cls._registry.keys())

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        from routing_router.mock_router import MockRouter

        cls.register("mock", lambda **kwargs: MockRouter(**kwargs))
        cls.register("default", lambda **kwargs: MockRouter(**kwargs))
