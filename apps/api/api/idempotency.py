"""Idempotency store protocol and in-memory implementation for request deduplication.

Owner: API Ingress
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, Tuple


class IdempotencyStore(Protocol):
    """Protocol for storing and retrieving responses for idempotent API requests."""

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached response payload for the idempotency key if still valid."""
        ...

    async def set(self, key: str, response: Dict[str, Any], ttl_seconds: int = 3600) -> None:
        """Store response payload against the idempotency key with TTL."""
        ...


class InMemoryIdempotencyStore:
    """In-memory thread-safe dictionary store for request deduplication."""

    def __init__(self) -> None:
        # Maps key -> (response_payload, expiry_timestamp_float)
        self._store: Dict[str, Tuple[Dict[str, Any], float]] = {}

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).timestamp()
        if key in self._store:
            payload, expiry = self._store[key]
            if now <= expiry:
                return payload
            # Expired
            del self._store[key]
        return None

    async def set(self, key: str, response: Dict[str, Any], ttl_seconds: int = 3600) -> None:
        expiry = datetime.now(timezone.utc).timestamp() + ttl_seconds
        self._store[key] = (response, expiry)

    def clear(self) -> None:
        self._store.clear()
