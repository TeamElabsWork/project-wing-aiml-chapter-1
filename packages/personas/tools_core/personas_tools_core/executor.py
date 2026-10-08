"""ToolExecutor orchestrating tool scope validation, risk classification, approval, and execution.

Owner: C3
"""

import inspect
from typing import Optional

from contracts.models import (
    ActionRequest,
    ApprovalRequest,
    RiskLevel,
    RouteDecision,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from safety_approval.manager import ApprovalManager
from safety_risk_classifier.classifier import RiskClassifier

from personas_tools_core.enforcer import ToolScopeEnforcer
from personas_tools_core.registry import ToolRegistry


class ToolExecutor:
    """Safely executes ToolCalls with scope validation, risk classification, and approval gating."""

    def __init__(
        self,
        tool_scope_enforcer: ToolScopeEnforcer,
        risk_classifier: RiskClassifier,
        approval_manager: ApprovalManager,
    ) -> None:
        self.tool_scope_enforcer = tool_scope_enforcer
        self.risk_classifier = risk_classifier
        self.approval_manager = approval_manager

    async def execute(
        self,
        tool_call: ToolCall,
        decision: RouteDecision,
        caller_persona: str,
    ) -> ToolResult:
        # 1. Verify tool exists in catalog
        spec: Optional[ToolSpec] = ToolRegistry.get_spec(tool_call.tool_name)
        func = ToolRegistry.get(tool_call.tool_name)
        if not spec or not func:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                ok=False,
                error=f"Tool '{tool_call.tool_name}' not found in registry.",
            )

        # 2. Build ActionRequest
        action = ActionRequest(
            call_id=tool_call.call_id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            caller_persona=caller_persona,
        )

        # 3. Enforce tool scope
        try:
            self.tool_scope_enforcer.enforce(action, decision.tool_scope)
        except PermissionError as e:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                ok=False,
                error=str(e),
            )

        # 4. Classify risk
        risk: RiskLevel = self.risk_classifier.classify(action, spec=spec)
        action = ActionRequest(
            call_id=action.call_id,
            tool_name=action.tool_name,
            arguments=action.arguments,
            caller_persona=action.caller_persona,
            risk_assessment=risk,
        )

        # 5. Check if approval is required:
        # - Destructive actions ALWAYS require approval regardless of surface or autonomy!
        # - Risk level >= medium requires approval.
        # - Autonomy supervised or read_only requires approval for write or external side effects.
        requires_approval = False
        reason = ""

        if spec.destructive:
            requires_approval = True
            reason = f"Tool '{spec.name}' is marked as destructive and always requires explicit approval."
        elif risk in ("medium", "high", "critical"):
            requires_approval = True
            reason = f"Tool '{spec.name}' has assessed risk tier '{risk}'."
        elif decision.autonomy in ("supervised", "read_only") and spec.side_effects in (
            "write",
            "external",
        ):
            requires_approval = True
            reason = (
                f"Tool '{spec.name}' has side effects '{spec.side_effects}' "
                f"which is restricted under autonomy mode '{decision.autonomy}'."
            )

        # 6. Request approval if needed
        if requires_approval:
            approval_req = ApprovalRequest(
                request_id=f"appr-{tool_call.call_id}",
                action=action,
                risk_level=risk,
                reason=reason,
                required_role="user" if risk != "critical" else "admin",
            )
            approval_resp = await self.approval_manager.request_approval(approval_req)
            if not approval_resp.approved:
                return ToolResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    ok=False,
                    error=approval_resp.feedback or f"Approval denied for tool '{spec.name}'.",
                )

        # 7. Execute tool callable
        try:
            if inspect.iscoroutinefunction(func):
                output = await func(**tool_call.arguments)
            else:
                output = func(**tool_call.arguments)

            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                ok=True,
                output=output,
            )
        except Exception as e:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                ok=False,
                error=f"Tool execution failed with exception: {str(e)}",
            )
