"""Memory retriever interface and stub.

Owner: E3
"""

from typing import Any, Callable, Dict, List, Optional, Protocol

from contracts.models import MemoryNode
from memory_store.base import MemoryRepository


class MemoryRetriever(Protocol):
    """Protocol for fetching relevant historical cross-surface memories."""

    async def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        surface: Optional[str] = None,
        limit: int = 3,
        context: Optional[Dict[str, Any]] = None,
        project_tag: Optional[str] = None,
    ) -> List[MemoryNode]:
        """Query memory store for contextually relevant nodes."""
        ...


class StubMemoryRetriever:
    """Working stub memory retriever forwarding to the repository."""

    def __init__(self, repository: MemoryRepository) -> None:
        self.repository = repository

    async def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        surface: Optional[str] = None,
        limit: int = 3,
        context: Optional[Dict[str, Any]] = None,
        project_tag: Optional[str] = None,
    ) -> List[MemoryNode]:
        # TODO (E3 Memory Retriever Owner): Implement hybrid lexical + dense vector
        # retrieval, cross-surface recency decay re-ranking, and MMR diversification.
        return await self.repository.search(
            query=query,
            user_id=user_id,
            surface=surface,
            limit=limit,
            project_tag=project_tag,
        )


class MemoryRetrieverRegistry:
    """Registry allowing memory retriever implementations to be selected."""

    _registry: Dict[str, Callable[..., MemoryRetriever]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., MemoryRetriever]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> MemoryRetriever:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"MemoryRetriever '{name}' not found. Available retrievers: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        cls.register("stub", lambda **kwargs: StubMemoryRetriever(**kwargs))
        cls.register("default", lambda **kwargs: StubMemoryRetriever(**kwargs))
        cls.register("unset", lambda **kwargs: StubMemoryRetriever(**kwargs))


MemoryRetrieverRegistry.register_defaults()
