"""Approval management subsystem.

Owner: D2
"""

from datetime import datetime, timezone
from typing import Protocol

from contracts.models import ApprovalRequest, ApprovalResponse


class ApprovalManager(Protocol):
    """Protocol for requesting action approvals."""

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Process an approval request synchronously or asynchronously."""
        ...


class AutoApproveStub:
    """Stub implementation that automatically approves all requests."""

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        # TODO (D2 Approval Owner): Implement interactive chat prompts
        # (Slack/Telegram buttons, CLI prompts) for human-in-the-loop approvals.
        return ApprovalResponse(
            request_id=request.request_id,
            approved=True,
            approver_id="auto-policy-stub",
            feedback="Auto-approved by default stub policy.",
            timestamp=datetime.now(timezone.utc),
        )
