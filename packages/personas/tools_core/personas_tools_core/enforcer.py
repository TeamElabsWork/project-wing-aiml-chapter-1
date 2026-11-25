"""Tool scope enforcer preventing actions outside the route-granted tool_scope.

Owner: C3
"""

import fnmatch
from typing import List, Optional, Protocol

from contracts.models import ActionRequest, ToolSpec


class ToolScopeEnforcerProtocol(Protocol):
    """Protocol for validating tool actions against allowed tool scopes."""

    def is_allowed(self, tool_name: str, allowed_scope: List[str]) -> bool:
        """Check if a tool is within the permitted scope."""
        ...

    def enforce(self, action: ActionRequest, allowed_scope: List[str]) -> None:
        """Raise PermissionError if the action is not in allowed_scope."""
        ...


class ToolScopeEnforcer:
    """Enforces that an ActionRequest matches the RouteDecision tool_scope."""

    def is_allowed(self, tool_name: str, allowed_scope: List[str]) -> bool:
        """Check if tool_name matches any allowed scope (supports wildcards, prefixes, and scopes)."""
        if not tool_name or not tool_name.strip():
            return False

        tool_norm = tool_name.strip().lower()

        # Try to resolve tool specification to check against required_scopes
        spec: Optional[ToolSpec] = None
        try:
            from personas_tools_core.registry import ToolRegistry

            spec = ToolRegistry.get_spec(tool_norm)
        except Exception:
            spec = None

        tool_scopes = {tool_norm}
        if spec and spec.required_scopes:
            tool_scopes.update(s.lower() for s in spec.required_scopes)

        for pattern in allowed_scope:
            pat_norm = pattern.strip().lower()
            if pat_norm == "*":
                return True

            # Direct equality against tool name or any required scope
            if pat_norm in tool_scopes:
                return True

            # Glob / Wildcard matching (e.g. 'git:*', 'git_*', 'git*')
            if fnmatch.fnmatchcase(tool_norm, pat_norm):
                return True

            # Check wildcard pattern against tool required scopes
            for req_scope in tool_scopes:
                if fnmatch.fnmatchcase(req_scope, pat_norm):
                    return True

            # Handle 'prefix:*' style where tool might be 'prefix_something' or 'prefix'
            if pat_norm.endswith(":*"):
                prefix = pat_norm[:-2]
                if (
                    tool_norm == prefix
                    or tool_norm.startswith(f"{prefix}_")
                    or tool_norm.startswith(f"{prefix}:")
                ):
                    return True
                for req_scope in tool_scopes:
                    if (
                        req_scope == prefix
                        or req_scope.startswith(f"{prefix}_")
                        or req_scope.startswith(f"{prefix}:")
                    ):
                        return True

        return False

    def enforce(self, action: ActionRequest, allowed_scope: List[str]) -> None:
        if not self.is_allowed(action.tool_name, allowed_scope):
            raise PermissionError(
                f"Tool '{action.tool_name}' is not permitted by active tool scope {allowed_scope}."
            )
