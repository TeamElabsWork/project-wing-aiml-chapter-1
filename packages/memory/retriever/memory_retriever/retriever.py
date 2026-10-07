"""Memory retriever interface and stub.

Owner: E3
"""

from typing import Any, Dict, List, Optional, Protocol

from contracts.models import MemoryNode
from memory_store.base import MemoryRepository


class MemoryRetriever(Protocol):
    """Protocol for fetching relevant historical cross-surface memories."""

    def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        surface: Optional[str] = None,
        limit: int = 3,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryNode]:
        """Query memory store for contextually relevant nodes."""
        ...


class StubMemoryRetriever:
    """Working stub memory retriever forwarding to the repository."""

    def __init__(self, repository: MemoryRepository) -> None:
        self.repository = repository

    def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        surface: Optional[str] = None,
        limit: int = 3,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryNode]:
        # TODO (E3 Memory Retriever Owner): Implement hybrid lexical + dense vector
        # retrieval, cross-surface recency decay re-ranking, and MMR diversification.
        return self.repository.search(query=query, user_id=user_id, surface=surface, limit=limit)
