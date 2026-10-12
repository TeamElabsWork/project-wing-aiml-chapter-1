"""EchoRuntime and ScriptedRuntime stubs executing persona turns.

Owner: C2
"""

from typing import Any, AsyncIterator, Dict, List, Optional

from contracts.models import (
    ActionRequest,
    ApprovalRequest,
    ContextBundle,
    Persona,
    RequestEnvelope,
    RouteDecision,
    RuntimeResult,
    TokenUsage,
    ToolCall,
    ToolResult,
)


class EchoRuntime:
    """Working stub agent runtime that echoes inputs formatted according to persona role."""

    async def execute(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        context: Optional[ContextBundle] = None,
        **kwargs: Any,
    ) -> RuntimeResult:
        # TODO (C2 Runtime Owner): Implement actual multi-step ReAct or plan-execute loop,
        # integrating with ToolRegistry and LLMProvider.
        if context is not None:
            history_count = len(context.history)
            memory_count = len(context.memory)
            budget = context.token_budget
            context_line = f"(context: {history_count} history, {memory_count} memory nodes, budget {budget} tokens)"
        else:
            history_count = len(session_history) if session_history else 0
            context_line = (
                f"(Context: {history_count} previous turn(s) in session {envelope.session_id})"
            )

        surface_type = envelope.surface_context.surface_type

        reply_text = (
            f"[{persona.name} | Surface: {surface_type} | Autonomy: {decision.autonomy}]\n"
            f'Acknowledged request: "{envelope.raw_text}"\n'
            f"{context_line}"
        )

        prompt_text = envelope.raw_text + (context.persona_prompt if context else "")
        prompt_tokens = len(prompt_text) // 4
        completion_tokens = len(reply_text) // 4
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated=True,
        )

        return RuntimeResult(
            reply_text=reply_text,
            tool_results=[],
            pending_approval=None,
            error=None,
            usage=usage,
        )

    async def stream(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        context: Optional[ContextBundle] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream echo response in chunked tokens."""
        res = await self.execute(
            envelope=envelope,
            decision=decision,
            persona=persona,
            session_history=session_history,
            tool_executor=tool_executor,
            context=context,
            **kwargs,
        )
        words = res.reply_text.split(" ")
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
        context: Optional[ContextBundle] = None,
        **kwargs: Any,
    ) -> RuntimeResult:
        raw_lower = envelope.raw_text.lower()
        tool_results: List[ToolResult] = []
        pending_approval: Optional[ApprovalRequest] = None
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
            tool_results.append(result)

            if result.pending:
                req_id = f"appr-{tool_call.call_id}"
                # Retrieve from approval_manager if possible, else create stub request
                app_mgr = getattr(tool_executor, "approval_manager", None)
                if app_mgr and hasattr(app_mgr, "get_pending"):
                    pending_approval = await app_mgr.get_pending(req_id)
                if not pending_approval:
                    pending_approval = ApprovalRequest(
                        request_id=req_id,
                        action=ActionRequest(
                            call_id=tool_call.call_id,
                            tool_name=tool_name,
                            arguments=tool_args,
                            caller_persona=persona.id,
                        ),
                        reason=result.error or f"Action '{tool_name}' requires human approval.",
                    )
                tool_result_str = (
                    f"Action '{tool_name}' is paused awaiting approval. Request ID: {req_id}"
                )
            elif result.ok:
                tool_result_str = (
                    f"Tool '{result.tool_name}' executed successfully: {result.output}"
                )
            else:
                tool_result_str = f"Tool '{result.tool_name}' failed or was blocked: {result.error}"

        reply_text = (
            f"[{persona.name} (Scripted) | Autonomy: {decision.autonomy}]\n"
            f'Request: "{envelope.raw_text}"\n'
            f"Result: {tool_result_str}"
        )

        prompt_text = envelope.raw_text + (context.persona_prompt if context else "")
        prompt_tokens = len(prompt_text) // 4
        completion_tokens = len(reply_text) // 4
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated=True,
        )

        return RuntimeResult(
            reply_text=reply_text,
            tool_results=tool_results,
            pending_approval=pending_approval,
            error=None,
            usage=usage,
        )

    async def stream(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        context: Optional[ContextBundle] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        res = await self.execute(
            envelope=envelope,
            decision=decision,
            persona=persona,
            session_history=session_history,
            tool_executor=tool_executor,
            context=context,
            **kwargs,
        )
        for chunk in res.reply_text.splitlines(keepends=True):
            yield chunk
