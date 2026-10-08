"""EchoRuntime and ScriptedRuntime stubs executing persona turns.

Owner: C2
"""

from typing import Any, AsyncIterator, Dict, List, Optional

from contracts.models import Persona, RequestEnvelope, RouteDecision, ToolCall, ToolResult

from personas_runtime.base import RuntimeRegistry


class EchoRuntime:
    """Working stub agent runtime that echoes inputs formatted according to persona role."""

    async def execute(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
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

    async def stream(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream echo response in chunked tokens."""
        text = await self.execute(
            envelope=envelope,
            decision=decision,
            persona=persona,
            session_history=session_history,
            tool_executor=tool_executor,
            **kwargs,
        )
        words = text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")


class ScriptedRuntime:
    """Demonstrates and tests executing tool calls via ToolExecutor."""

    async def execute(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        raw_lower = envelope.raw_text.lower()
        tool_result_str = "No tool invoked."

        if tool_executor:
            # Determine which tool to test calling based on prompt
            if "wipe" in raw_lower or "destructive" in raw_lower or "delete" in raw_lower:
                tool_name = "destructive_wipe"
                tool_args = {"target": "all"}
            elif "pr" in raw_lower or "github" in raw_lower:
                tool_name = "github_pr"
                tool_args = {"title": envelope.raw_text}
            else:
                tool_name = "echo"
                tool_args = {"message": envelope.raw_text}

            tool_call = ToolCall(
                call_id="call-scripted-001",
                tool_name=tool_name,
                arguments=tool_args,
            )

            result: ToolResult = await tool_executor.execute(
                tool_call=tool_call,
                decision=decision,
                caller_persona=persona.id,
            )

            if result.ok:
                tool_result_str = (
                    f"Tool '{result.tool_name}' executed successfully: {result.output}"
                )
            else:
                tool_result_str = f"Tool '{result.tool_name}' failed or was blocked: {result.error}"

        return (
            f"[{persona.name} (Scripted) | Autonomy: {decision.autonomy}]\n"
            f'Request: "{envelope.raw_text}"\n'
            f"Result: {tool_result_str}"
        )

    async def stream(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        text = await self.execute(
            envelope=envelope,
            decision=decision,
            persona=persona,
            session_history=session_history,
            tool_executor=tool_executor,
            **kwargs,
        )
        for chunk in text.splitlines(keepends=True):
            yield chunk


RuntimeRegistry.register_defaults()
