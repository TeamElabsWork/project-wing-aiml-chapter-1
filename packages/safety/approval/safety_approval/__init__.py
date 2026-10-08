"""Safety approval package."""

from safety_approval.manager import (
    ApprovalManager,
    ApprovalManagerRegistry,
    AutoApproveStub,
    DenyAllApprovalStub,
)

__all__ = [
    "ApprovalManager",
    "ApprovalManagerRegistry",
    "AutoApproveStub",
    "DenyAllApprovalStub",
]
