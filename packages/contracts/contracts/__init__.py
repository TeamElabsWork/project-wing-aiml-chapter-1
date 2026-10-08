"""Shared contracts package for Surface-Aware Agent Orchestration.

Version: 0.2.0
"""

from contracts.models import (
    KNOWN_SURFACES,
    ActionRequest,
    ApprovalRequest,
    ApprovalResponse,
    Autonomy,
    ExecutionTarget,
    MemoryNode,
    Persona,
    PolicyEvaluation,
    RequestEnvelope,
    Response,
    ResponseStatus,
    RiskLevel,
    RouteDecision,
    SessionState,
    SideEffects,
    SurfaceContext,
    SurfaceType,
    ToolCall,
    ToolResult,
    ToolSpec,
    UrgencyLevel,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "ActionRequest",
    "ApprovalRequest",
    "ApprovalResponse",
    "Autonomy",
    "ExecutionTarget",
    "KNOWN_SURFACES",
    "MemoryNode",
    "Persona",
    "PolicyEvaluation",
    "RequestEnvelope",
    "Response",
    "ResponseStatus",
    "RiskLevel",
    "RouteDecision",
    "SessionState",
    "SideEffects",
    "SurfaceContext",
    "SurfaceType",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "UrgencyLevel",
]
