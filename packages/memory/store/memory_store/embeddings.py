"""Embedding provider abstraction and deterministic mock implementation.

Owner: E1
"""

import hashlib
import math
from typing import Any, Callable, Dict, List, Protocol


class EmbeddingProvider(Protocol):
    """Protocol for vector embedding models."""

    @property
    def dimensions(self) -> int:
        """Dimensionality of the produced vector embeddings."""
        ...

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Compute dense vector embeddings for input strings."""
        ...


class MockEmbeddingProvider:
    """Deterministic in-memory embedding provider producing unit-normalized vectors."""

    def __init__(self, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: List[str]) -> List[List[float]]:
        # TODO (E1 Memory Owner): Replace with real embedding model provider
        # (OpenAI text-embedding-3, Voyage, FastEmbed, or HuggingFace).
        embeddings: List[List[float]] = []
        for text in texts:
            vec: List[float] = []
            for i in range(self._dimensions):
                # Deterministic hash seeded by text and dimension index
                h = int(hashlib.md5(f"{text}_{i}".encode("utf-8")).hexdigest()[:8], 16)
                val = ((h % 2000) - 1000) / 1000.0
                vec.append(val)

            # L2 normalize
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            embeddings.append([x / norm for x in vec])

        return embeddings


class EmbeddingProviderRegistry:
    """Registry allowing embedding providers to be configured and selected."""

    _registry: Dict[str, Callable[..., EmbeddingProvider]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., EmbeddingProvider]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> EmbeddingProvider:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"EmbeddingProvider '{name}' not found. Registered providers: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        cls.register("mock", lambda **kwargs: MockEmbeddingProvider(**kwargs))
        cls.register("unset", lambda **kwargs: MockEmbeddingProvider(**kwargs))
        cls.register("default", lambda **kwargs: MockEmbeddingProvider(**kwargs))


EmbeddingProviderRegistry.register_defaults()
