"""Memory writer interface and stub.

Owner: E2
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Protocol

from contracts.models import MemoryNode, RequestEnvelope, RouteDecision
from memory_store.base import MemoryRepository


class MemoryWriter(Protocol):
    """Protocol for recording interaction turns into memory nodes."""

    def write_interaction(
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

    def write_interaction(
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
        self.repository.save(node)
        return node
