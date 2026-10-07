"""Tool scope enforcer preventing actions outside the route-granted tool_scope.

Owner: C3
"""

from typing import List, Protocol

from contracts.models import ActionRequest


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
        # TODO (C3 Tools Core Owner): Add wildcard scopes (e.g., 'git:*')
        # and parameter-level constraint filters.
        return "*" in allowed_scope or tool_name.lower() in [s.lower() for s in allowed_scope]

    def enforce(self, action: ActionRequest, allowed_scope: List[str]) -> None:
        if not self.is_allowed(action.tool_name, allowed_scope):
            raise PermissionError(
                f"Tool '{action.tool_name}' is not permitted by active tool scope {allowed_scope}."
            )
