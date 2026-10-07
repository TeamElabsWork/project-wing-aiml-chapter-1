"""Memory repository interface and backend registry.

Owner: E1
"""

from typing import Any, Callable, Dict, List, Optional, Protocol

from contracts.models import MemoryNode


class MemoryRepository(Protocol):
    """Protocol for persisting and querying cross-surface MemoryNode entities."""

    def save(self, node: MemoryNode) -> None:
        """Persist a memory node."""
        ...

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        surface: Optional[str] = None,
        limit: int = 5,
    ) -> List[MemoryNode]:
        """Search memory nodes matching query keywords or similarity."""
        ...

    def get_by_id(self, node_id: str) -> Optional[MemoryNode]:
        """Fetch a specific node by its ID."""
        ...

    def list_all(self, user_id: Optional[str] = None) -> List[MemoryNode]:
        """List all stored memory nodes, optionally filtered by user."""
        ...


class MemoryStoreRegistry:
    """Registry allowing memory store backends (in-memory, postgres-pgvector, redis) to be selected."""

    _registry: Dict[str, Callable[..., MemoryRepository]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., MemoryRepository]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> MemoryRepository:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"Memory store backend '{name}' not found. Available backends: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)
