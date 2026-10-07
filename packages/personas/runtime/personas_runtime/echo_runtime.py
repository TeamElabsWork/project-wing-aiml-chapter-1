"""EchoRuntime stub executing persona turns by generating structured echo responses.

Owner: C2
"""

from typing import Any, Dict, List, Optional

from contracts.models import Persona, RequestEnvelope, RouteDecision

from personas_runtime.base import RuntimeRegistry


class EchoRuntime:
    """Working stub agent runtime that echoes inputs formatted according to persona role."""

    def execute(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> str:
        # TODO (C2 Runtime Owner): Implement actual multi-step ReAct or plan-execute loop,
        # integrating with ToolRegistry and LLMProvider.
        history_count = len(session_history) if session_history else 0
        surface_type = envelope.surface_context.surface_type

        return (
            f"[{persona.name} | Surface: {surface_type} | Autonomy: {decision.autonomy}]\n"
            f'Acknowledged request: "{envelope.raw_text}"\n'
            f"(Context: {history_count} previous turn(s) in session {envelope.session_id})"
        )


RuntimeRegistry.register("echo", lambda **kwargs: EchoRuntime())
RuntimeRegistry.register("default", lambda **kwargs: EchoRuntime())
