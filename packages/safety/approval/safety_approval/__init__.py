"""Safety approval package."""

from safety_approval.manager import (
    ApprovalManager,
    ApprovalManagerRegistry,
    AutoApproveStub,
    CLIApprovalManager,
    DenyAllApprovalStub,
    PendingApprovalManager,
)

__all__ = [
    "ApprovalManager",
    "ApprovalManagerRegistry",
    "AutoApproveStub",
    "CLIApprovalManager",
    "DenyAllApprovalStub",
    "PendingApprovalManager",
]
