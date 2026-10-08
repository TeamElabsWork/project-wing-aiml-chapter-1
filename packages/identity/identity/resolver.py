"""Identity resolution module.

Owner: A4
"""

from typing import Any, Callable, Dict, Protocol, Tuple


class IdentityResolver(Protocol):
    """Protocol for mapping surface-specific external IDs to internal canonical user IDs."""

    def resolve_user(self, surface: str, external_id: str) -> str:
        """Resolve a surface + external identifier into a canonical user ID."""
        ...


class InMemoryIdentityResolver:
    """In-memory stub implementation of IdentityResolver with fallback mapping."""

    def __init__(self, initial_mappings: Dict[Tuple[str, str], str] | None = None) -> None:
        # Key: (surface, external_id) -> canonical_user_id
        self._mappings: Dict[Tuple[str, str], str] = initial_mappings or {
            ("cli", "local-user"): "usr-dev-001",
            ("telegram", "12345678"): "usr-dev-001",
            ("slack", "U123456"): "usr-dev-001",
        }

    def resolve_user(self, surface: str, external_id: str) -> str:
        # TODO (A4 Identity Owner): Implement persistent mapping, OAuth/SSO linking,
        # or directory lookups.
        key = (surface.lower(), external_id)
        if key in self._mappings:
            return self._mappings[key]

        # Deterministic fallback canonical ID
        canonical_id = f"usr-{surface.lower()}-{external_id}"
        self._mappings[key] = canonical_id
        return canonical_id

    def register_mapping(self, surface: str, external_id: str, canonical_user_id: str) -> None:
        """Register a known mapping for testing or seeding."""
        self._mappings[(surface.lower(), external_id)] = canonical_user_id


class IdentityResolverRegistry:
    """Registry allowing identity resolver backends to be configured and selected."""

    _registry: Dict[str, Callable[..., IdentityResolver]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., IdentityResolver]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> IdentityResolver:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"IdentityResolver '{name}' not found in registry. Registered: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        cls.register("in_memory", lambda **kwargs: InMemoryIdentityResolver(**kwargs))
        cls.register("default", lambda **kwargs: InMemoryIdentityResolver(**kwargs))
        cls.register("unset", lambda **kwargs: InMemoryIdentityResolver(**kwargs))
