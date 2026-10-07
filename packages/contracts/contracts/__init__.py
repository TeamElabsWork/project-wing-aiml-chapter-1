"""Shared contracts package for Surface-Aware Agent Orchestration.

Version: 0.1.0
"""

from contracts.models import (
    ActionRequest,
    ApprovalRequest,
    ApprovalResponse,
    MemoryNode,
    Persona,
    RequestEnvelope,
    Response,
    RouteDecision,
    SurfaceContext,
    ToolSpec,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ActionRequest",
    "ApprovalRequest",
    "ApprovalResponse",
    "MemoryNode",
    "Persona",
    "RequestEnvelope",
    "Response",
    "RouteDecision",
    "SurfaceContext",
    "ToolSpec",
]
