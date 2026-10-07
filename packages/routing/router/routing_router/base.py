"""Router protocol and router registry.

Owner: B2
"""

from typing import Any, Callable, Dict, List, Protocol

from contracts.models import MemoryNode, RequestEnvelope, RouteDecision


class Router(Protocol):
    """Protocol implemented by routing engines (LLM-based, heuristic, or hybrid)."""

    def route(
        self,
        envelope: RequestEnvelope,
        session_state: Dict[str, Any],
        surface_policy: Dict[str, Any],
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
