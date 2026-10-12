"""ContextBuilder protocol and registry.

Owner IDs: C2 + E3
"""

from typing import Any, Callable, Dict, List, Protocol

from contracts.models import (
    ContextBundle,
    MemoryNode,
    Persona,
    PolicyEvaluation,
    RequestEnvelope,
    RouteDecision,
    SessionState,
)


class ContextBuilder(Protocol):
    """Protocol for assembling context bundles for agent runtime execution.

    Owner IDs: C2 (Runtime Owner) + E3 (Memory Owner)
    """

    async def build(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        policy: PolicyEvaluation,
        session_state: SessionState,
        memory: List[MemoryNode],
        **kwargs: Any,
    ) -> ContextBundle:
        """Assemble ContextBundle for the agent runtime."""
        ...


class ContextBuilderRegistry:
    """Registry for pluggable ContextBuilder backends."""

    _registry: Dict[str, Callable[..., ContextBuilder]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., ContextBuilder]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> ContextBuilder:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"ContextBuilder '{name}' not found. Available builders: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        from personas_context_builder.passthrough import PassthroughContextBuilder

        cls.register("passthrough", lambda **kwargs: PassthroughContextBuilder(**kwargs))
        cls.register("default", lambda **kwargs: PassthroughContextBuilder(**kwargs))
        cls.register("unset", lambda **kwargs: PassthroughContextBuilder(**kwargs))
