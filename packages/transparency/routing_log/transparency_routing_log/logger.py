"""Transparency logging for routing decisions.

Owner: F1
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Protocol

from contracts.models import RouteDecision


class RoutingLoggerProtocol(Protocol):
    """Protocol for formatting and emitting routing explanations."""

    def render_explanation(self, decision: RouteDecision) -> str:
        """Render human-readable line: 'Summoned <persona> because ...'."""
        ...

    def to_structured_log(
        self, decision: RouteDecision, extra: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Produce structured dictionary suitable for JSON logging."""
        ...

    def emit_log(self, decision: RouteDecision, extra: Dict[str, Any] | None = None) -> str:
        """Returns JSON string for structured logging sinks."""
        ...


class RoutingLogger:
    """Renders human-facing 'Summoned <persona> because ...' line and structured logs."""

    def render_explanation(self, decision: RouteDecision) -> str:
        # TODO (F1 Transparency Owner): Customize styling per surface (e.g. markdown quotes,
        # terminal colors, or Slack attachments).
        return (
            f"Summoned {decision.persona} because {decision.reasoning} "
            f"(autonomy: {decision.autonomy}, confidence: {decision.confidence:.2f})"
        )

    def to_structured_log(
        self, decision: RouteDecision, extra: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        log_entry = {
            "event": "routing_decision",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "persona": decision.persona,
            "autonomy": decision.autonomy,
            "confidence": decision.confidence,
            "tool_scope": decision.tool_scope,
            "reasoning": decision.reasoning,
            **(extra or {}),
        }
        return log_entry

    def emit_log(self, decision: RouteDecision, extra: Dict[str, Any] | None = None) -> str:
        """Returns JSON string for structured logging sinks."""
        return json.dumps(self.to_structured_log(decision, extra))
