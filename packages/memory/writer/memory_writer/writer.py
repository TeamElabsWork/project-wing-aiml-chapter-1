"""Memory writer interface and stub.

Owner: E2
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Protocol

from contracts.models import MemoryNode, RequestEnvelope, RouteDecision
from memory_store.base import MemoryRepository


class MemoryWriter(Protocol):
    """Protocol for recording interaction turns into memory nodes."""

    async def write_interaction(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        reply_text: str,
        extra_metadata: Dict[str, Any] | None = None,
    ) -> MemoryNode:
        """Extract memory facts and persist to repository."""
        ...


class StubMemoryWriter:
    """Working stub memory writer creating a concise summary and saving to repository."""

    def __init__(self, repository: MemoryRepository) -> None:
        self.repository = repository

    async def write_interaction(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        reply_text: str,
        extra_metadata: Dict[str, Any] | None = None,
    ) -> MemoryNode:
        # TODO (E2 Memory Writer Owner): Implement LLM-based fact extraction,
        # entity resolution, and dense embedding generation.
        node = MemoryNode(
            node_id=f"mem-{uuid.uuid4().hex[:10]}",
            user_id=envelope.user_id,
            surface=envelope.surface_context.surface_type,
            project_tag=envelope.metadata.get("project_tag"),
            persona=decision.persona,
            summary=f"User asked: '{envelope.raw_text[:60]}...' | Handled by {decision.persona}",
            embedding=None,
            timestamp=datetime.now(timezone.utc),
            metadata={
                "message_id": envelope.message_id,
                "session_id": envelope.session_id,
                "confidence": decision.confidence,
                **(extra_metadata or {}),
            },
        )
        await self.repository.save(node)
        return node


class MemoryWriterRegistry:
    """Registry allowing memory writer implementations to be selected."""

    _registry: Dict[str, Callable[..., MemoryWriter]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., MemoryWriter]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> MemoryWriter:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"MemoryWriter '{name}' not found. Available writers: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        cls.register("stub", lambda **kwargs: StubMemoryWriter(**kwargs))
        cls.register("default", lambda **kwargs: StubMemoryWriter(**kwargs))
        cls.register("unset", lambda **kwargs: StubMemoryWriter(**kwargs))


MemoryWriterRegistry.register_defaults()
