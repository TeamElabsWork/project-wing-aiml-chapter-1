"""In-memory implementation of MemoryRepository.

Owner: E1
"""

from typing import Dict, List, Optional

from contracts.models import MemoryNode

from memory_store.base import MemoryRepository


class InMemoryMemoryRepository(MemoryRepository):
    """In-memory stub repository storing MemoryNode instances in Python dictionaries."""

    def __init__(self) -> None:
        self._nodes: Dict[str, MemoryNode] = {}

    async def save(self, node: MemoryNode) -> None:
        # TODO (E1 Memory Store Owner): Implement real Postgres+pgvector queries,
        # connection pooling, and vector indexing using pgvector.
        self._nodes[node.node_id] = node

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        surface: Optional[str] = None,
        limit: int = 5,
        query_embedding: Optional[List[float]] = None,
        project_tag: Optional[str] = None,
    ) -> List[MemoryNode]:
        results: List[MemoryNode] = []
        lowered_q = query.lower()

        for node in reversed(list(self._nodes.values())):
            if user_id and node.user_id != user_id:
                continue
            if surface and node.surface != surface:
                continue
            if project_tag and node.project_tag != project_tag:
                continue
            # Simple keyword match or fallback inclusion
            if not query or lowered_q in node.summary.lower():
                results.append(node)
            elif any(lowered_q in str(v).lower() for v in node.metadata.values()):
                results.append(node)

            if len(results) >= limit:
                break

        # Fallback to returning most recent nodes if strict keyword search yielded nothing
        if not results and self._nodes:
            candidates = [
                n
                for n in reversed(list(self._nodes.values()))
                if (not user_id or n.user_id == user_id)
                and (not project_tag or n.project_tag == project_tag)
            ]
            results = candidates[:limit]

        return results

    async def get_by_id(self, node_id: str) -> Optional[MemoryNode]:
        return self._nodes.get(node_id)

    async def list_all(self, user_id: Optional[str] = None) -> List[MemoryNode]:
        if user_id:
            return [n for n in self._nodes.values() if n.user_id == user_id]
        return list(self._nodes.values())
