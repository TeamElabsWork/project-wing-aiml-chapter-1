"""Transparency logging for routing decisions.

Owner: F1
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Protocol

from contracts.models import RouteDecision

from .formatters import (
    format_markdown,
    format_terminal,
    new_correlation_id,
)


class RoutingLoggerProtocol(Protocol):
    """Protocol for formatting and emitting routing explanations."""

    def render_explanation(self, decision: RouteDecision) -> str:
        """Render human-readable line: 'Summoned <persona> because ...'."""
        ...

    def render_terminal(self, decision: RouteDecision, color: bool | None = None) -> str:
        """Render the explanation with ANSI colors for terminals."""
        ...

    def render_markdown(self, decision: RouteDecision) -> str:
        """Render the explanation as a markdown quote block."""
        ...

    def render_for_surface(self, decision: RouteDecision, surface: str) -> str:
        """Pick the best format for the given surface."""
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
        # Plain text, unchanged: existing callers and tests depend on this exact output.
        return (
            f"Summoned {decision.persona} because {decision.reasoning} "
            f"(autonomy: {decision.autonomy}, confidence: {decision.confidence:.2f})"
        )

    def render_terminal(self, decision: RouteDecision, color: bool | None = None) -> str:
        return format_terminal(
            str(decision.persona),
            str(decision.reasoning),
            str(decision.autonomy),
            float(decision.confidence),
            color=color,
        )

    def render_markdown(self, decision: RouteDecision) -> str:
        return format_markdown(
            str(decision.persona),
            str(decision.reasoning),
            str(decision.autonomy),
            float(decision.confidence),
        )

    def render_for_surface(self, decision: RouteDecision, surface: str) -> str:
        """CLI gets colored text; chat/web surfaces get markdown; unknown gets plain text."""
        if surface == "cli":
            return self.render_terminal(decision)
        if surface in ("slack", "telegram", "web"):
            return self.render_markdown(decision)
        return self.render_explanation(decision)

    def to_structured_log(
        self, decision: RouteDecision, extra: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        log_entry = {
            "event": "routing_decision",
            "level": "INFO",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": new_correlation_id(),
            "persona": decision.persona,
            "autonomy": decision.autonomy,
            "confidence": decision.confidence,
            "tool_scope": decision.tool_scope,
            "reasoning": decision.reasoning,
            "message": self.render_explanation(decision),
            **(extra or {}),
        }
        return log_entry

    def emit_log(self, decision: RouteDecision, extra: Dict[str, Any] | None = None) -> str:
        """Returns JSON string for structured logging sinks."""
        return json.dumps(self.to_structured_log(decision, extra))
