"""MockRouter returning a working, deterministic RouteDecision.

Owner: B2
"""

import re
from typing import Any, Dict, List, Optional

from contracts.models import MemoryNode, RequestEnvelope, RouteDecision

from routing_router.base import RouterRegistry


class MockRouter:
    """Working mock router returning a RouteDecision based on simple heuristics or fixed values."""

    def __init__(
        self,
        default_persona: str = "coder",
        default_autonomy: str = "semi",
        fixed_decision: Optional[RouteDecision] = None,
    ) -> None:
        self.default_persona = default_persona
        self.default_autonomy = default_autonomy
        self.fixed_decision = fixed_decision

    def route(
        self,
        envelope: RequestEnvelope,
        session_state: Dict[str, Any],
        surface_policy: Dict[str, Any],
        memory_context: List[MemoryNode],
    ) -> RouteDecision:
        # TODO (B2 Router Owner): Implement LLM-based structured routing,
        # few-shot exemplar retrieval from memory, and complex multi-agent delegation.
        if self.fixed_decision:
            return self.fixed_decision

        text = envelope.raw_text.lower()
        surface = envelope.surface_context.surface_type.lower()
        policy_autonomy = surface_policy.get("autonomy_recommendation", self.default_autonomy)

        def has_any(keywords: tuple[str, ...]) -> bool:
            return any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in keywords)

        if has_any(("research", "paper", "papers", "literature")):
            persona = "researcher"
            reasoning = f"Task requested research inquiry from surface '{surface}'."
            tools = ["echo"]
            autonomy = "semi"
        elif has_any(
            ("deploy", "ops", "server", "infra", "k8s", "outage", "incident", "production")
        ):
            persona = "ops"
            reasoning = (
                f"Task requested infrastructure/incident operations from surface '{surface}'."
            )
            tools = ["echo"]
            autonomy = "supervised"
        elif has_any(("readme", "documentation", "release notes", "draft")):
            persona = "writer"
            reasoning = f"Task requested documentation drafting from surface '{surface}'."
            tools = ["echo"]
            autonomy = "full"
        elif has_any(("code", "refactor", "function", "fix", "class", "test", "python")):
            persona = "coder"
            reasoning = f"Task requested software engineering from surface '{surface}'."
            tools = ["echo"]
            autonomy = "semi"
        else:
            persona = self.default_persona
            reasoning = f"Selected '{persona}' on surface '{surface}' (urgency: {surface_policy.get('is_urgent', False)})."
            tools = ["echo"]
            autonomy = policy_autonomy

        return RouteDecision(
            persona=persona,
            tool_scope=tools,
            autonomy=autonomy,
            confidence=0.95,
            reasoning=reasoning,
        )


# Register mock router by default
RouterRegistry.register("mock", lambda **kwargs: MockRouter(**kwargs))
RouterRegistry.register("default", lambda **kwargs: MockRouter(**kwargs))
