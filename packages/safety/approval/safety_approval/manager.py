"""Approval management subsystem.

Owner: D2
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Protocol

from contracts.models import ApprovalRequest, ApprovalResponse


class ApprovalManager(Protocol):
    """Protocol for requesting action approvals."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Process an approval request."""
        ...


class AutoApproveStub:
    """Stub implementation that automatically approves all requests."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        # TODO (D2 Approval Owner): Implement interactive chat prompts
        # (Slack/Telegram buttons, CLI prompts) for human-in-the-loop approvals.
        return ApprovalResponse(
            request_id=request.request_id,
            approved=True,
            approver_id="auto-policy-stub",
            feedback="Auto-approved by default stub policy.",
            timestamp=datetime.now(timezone.utc),
        )


class DenyAllApprovalStub:
    """Stub implementation that denies all approval requests for safety testing."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        return ApprovalResponse(
            request_id=request.request_id,
            approved=False,
            approver_id="deny-all-policy",
            feedback="Action rejected by DenyAllApprovalStub policy.",
            timestamp=datetime.now(timezone.utc),
        )


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
        cls.register("default", lambda **kwargs: AutoApproveStub())
        cls.register("unset", lambda **kwargs: AutoApproveStub())


ApprovalManagerRegistry.register_defaults()
