"""Approval management subsystem.

Owner: D2
"""

import builtins
import inspect
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Protocol

from contracts.models import ApprovalRequest, ApprovalResponse


class ApprovalManager(Protocol):
    """Protocol for requesting and processing action approvals."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Process or enqueue an approval request."""
        ...

    async def submit_decision(
        self, request_id: str, decision: ApprovalResponse
    ) -> Optional[ApprovalResponse]:
        """Submit an approval or rejection decision for a pending request."""
        ...

    async def get_pending(self, request_id: str) -> Optional[ApprovalRequest]:
        """Fetch a pending approval request by its ID."""
        ...


class AutoApproveStub:
    """Stub implementation that automatically approves all requests."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        return ApprovalResponse(
            request_id=request.request_id,
            approved=True,
            approver_id="auto-policy-stub",
            feedback="Auto-approved by default stub policy.",
            pending=False,
            timestamp=datetime.now(timezone.utc),
        )

    async def submit_decision(
        self, request_id: str, decision: ApprovalResponse
    ) -> Optional[ApprovalResponse]:
        return decision

    async def get_pending(self, request_id: str) -> Optional[ApprovalRequest]:
        return None


class DenyAllApprovalStub:
    """Stub implementation that denies all approval requests for safety testing."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        return ApprovalResponse(
            request_id=request.request_id,
            approved=False,
            approver_id="deny-all-policy",
            feedback="Action rejected by DenyAllApprovalStub policy.",
            pending=False,
            timestamp=datetime.now(timezone.utc),
        )

    async def submit_decision(
        self, request_id: str, decision: ApprovalResponse
    ) -> Optional[ApprovalResponse]:
        return decision

    async def get_pending(self, request_id: str) -> Optional[ApprovalRequest]:
        return None


class PendingApprovalManager:
    """Manages asynchronous human approval workflows by holding requests until decided."""

    def __init__(self) -> None:
        self._pending: Dict[str, ApprovalRequest] = {}
        self._decisions: Dict[str, ApprovalResponse] = {}
        self._execution_results: Dict[str, Any] = {}

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Enqueues request into pending table awaiting external authorization."""
        self._pending[request.request_id] = request
        return ApprovalResponse(
            request_id=request.request_id,
            approved=False,
            approver_id="pending-queue",
            feedback="Action queued awaiting human or operator authorization.",
            pending=True,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_pending(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._pending.get(request_id)

    async def submit_decision(
        self, request_id: str, decision: ApprovalResponse
    ) -> Optional[ApprovalResponse]:
        """Resolves a pending request. If approved, executes the stored ToolCall."""
        req = self._pending.get(request_id)
        if not req:
            return None

        self._decisions[request_id] = decision
        del self._pending[request_id]

        if decision.approved:
            # Re-run / resume the pending tool call using ToolRegistry
            from contracts.models import ToolResult
            from personas_tools_core.registry import ToolRegistry

            func = ToolRegistry.get(req.action.tool_name)
            if func:
                try:
                    if inspect.iscoroutinefunction(func):
                        output = await func(**req.action.arguments)
                    else:
                        output = func(**req.action.arguments)
                    tr = ToolResult(
                        call_id=req.action.call_id,
                        tool_name=req.action.tool_name,
                        ok=True,
                        output=output,
                        error=None,
                        denied=False,
                    )
                    self._execution_results[request_id] = tr
                except Exception as e:
                    tr = ToolResult(
                        call_id=req.action.call_id,
                        tool_name=req.action.tool_name,
                        ok=False,
                        output=None,
                        error=str(e),
                        denied=False,
                    )
                    self._execution_results[request_id] = tr
        else:
            from contracts.models import ToolResult

            tr = ToolResult(
                call_id=req.action.call_id,
                tool_name=req.action.tool_name,
                ok=False,
                output=None,
                error=decision.feedback or "Action rejected by human operator.",
                denied=True,
            )
            self._execution_results[request_id] = tr

        return decision

    @property
    def execution_results(self) -> Dict[str, Any]:
        """Access execution results dictionary."""
        return self._execution_results

    def get_execution_result(self, request_id: str) -> Optional[Any]:
        """Retrieve output of tool executed upon approval."""
        return self._execution_results.get(request_id)

    def list_pending(self) -> Dict[str, ApprovalRequest]:
        return dict(self._pending)


class CLIApprovalManager:
    """Interactive CLI approval manager prompting the operator via stdin.

    When an action requires approval, this manager prints a summary of the
    requested tool action and reads a ``y/n`` response from the terminal.
    Uses ``builtins.input`` so callers (and tests) can easily monkey-patch it.
    """

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Display an interactive CLI prompt and return the operator's decision."""
        print("\n" + "=" * 50)
        print("[APPROVAL REQUIRED]")
        print(f"  Tool:       {request.action.tool_name}")
        print(f"  Arguments:  {request.action.arguments}")
        print(f"  Risk Level: {request.risk_level}")
        print(f"  Reason:     {request.reason}")
        print("=" * 50)

        answer = builtins.input("Approve this action? [y/N]: ").strip().lower()
        approved = answer in ("y", "yes")

        return ApprovalResponse(
            request_id=request.request_id,
            approved=approved,
            approver_id="cli-operator",
            feedback="Approved by CLI operator." if approved else "Denied by CLI operator.",
            pending=False,
            timestamp=datetime.now(timezone.utc),
        )

    async def submit_decision(
        self, request_id: str, decision: ApprovalResponse
    ) -> Optional[ApprovalResponse]:
        return decision

    async def get_pending(self, request_id: str) -> Optional[ApprovalRequest]:
        return None


class ApprovalManagerRegistry:
    """Registry allowing approval managers to be configured and selected."""

    _registry: Dict[str, Callable[..., ApprovalManager]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., ApprovalManager]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> ApprovalManager:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"ApprovalManager '{name}' not found in registry. Registered managers: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        cls.register("auto_approve", lambda **kwargs: AutoApproveStub())
        cls.register("deny_all", lambda **kwargs: DenyAllApprovalStub())
        cls.register("pending", lambda **kwargs: PendingApprovalManager())
        cls.register("cli_interactive", lambda **kwargs: CLIApprovalManager())
        cls.register("default", lambda **kwargs: AutoApproveStub())
        cls.register("unset", lambda **kwargs: AutoApproveStub())
