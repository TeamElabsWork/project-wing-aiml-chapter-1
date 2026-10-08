"""Identity package: user mapping."""

from identity.resolver import (
    IdentityResolver,
    IdentityResolverRegistry,
    InMemoryIdentityResolver,
)

__all__ = ["IdentityResolver", "IdentityResolverRegistry", "InMemoryIdentityResolver"]
