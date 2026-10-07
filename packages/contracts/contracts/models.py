"""Shared Pydantic contracts for Surface-Aware Agent Orchestration.

These schemas are the single source of truth across all modules in the repository.
Every module may import contracts; no module may import another module's internal implementation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SurfaceContext(BaseModel):
    """Contextual metadata describing the surface from which an event originated.

    Different surfaces (CLI, Telegram, Slack, Web, etc.) impose different
    interaction constraints, urgency assumptions, and output capabilities.
    """

    model_config = ConfigDict(frozen=True)

    surface_type: str = Field(
        ...,
        description="Type of the surface, e.g., 'cli', 'telegram', 'slack', 'web'.",
    )
    client_id: str = Field(
        ...,
        description="Unique identifier for the surface client instance or app install.",
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="Identifier of the specific channel, chat room, or thread if applicable.",
    )
    is_interactive: bool = Field(
        default=True,
        description="Whether this surface supports synchronous multi-turn interaction.",
    )
    supports_markdown: bool = Field(
        default=True,
        description="Whether this surface natively renders markdown-formatted text.",
    )
    urgency_hint: Optional[str] = Field(
        default=None,
        description="Urgency hint inferred from the surface or client payload (e.g., 'high', 'normal').",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional surface-specific arbitrary key-value pairs (e.g., user agent, raw headers).",
    )


class RequestEnvelope(BaseModel):
    """Normalized request envelope produced by the gateway from raw surface input.

    Carries the user's message, identity, session state key, and surface context
    into the orchestration pipeline.
    """

    model_config = ConfigDict(frozen=True)

    message_id: str = Field(
        ...,
        description="Globally unique identifier for this incoming message event.",
    )
    session_id: str = Field(
        ...,
        description="Active session or conversation thread identifier.",
    )
    user_id: str = Field(
        ...,
        description="Resolved internal canonical user ID (resolved by the Identity module).",
    )
    raw_text: str = Field(
        ...,
        description="Raw, unformatted textual prompt or query entered by the user.",
    )
    surface_context: SurfaceContext = Field(
        ...,
        description="Surface properties and capabilities associated with this request.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary event metadata (e.g., traces, tags, client timestamps).",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the envelope was created by the gateway.",
    )


class RouteDecision(BaseModel):
    """Central routing contract deciding how an incoming request is dispatched.

    Produced by the router module after evaluating the task text, surface policies,
    session state, and retrieved memory. Keep this contract stable.
    """

    model_config = ConfigDict(frozen=True)

    persona: str = Field(
        ...,
        description="Identifier of the selected persona (e.g., 'coder', 'researcher', 'ops', 'writer').",
    )
    tool_scope: List[str] = Field(
        default_factory=list,
        description="List of tool names allowed to be invoked during the execution of this turn.",
    )
    autonomy: str = Field(
        default="semi",
        description="Autonomy mode granted: 'full', 'semi', 'read_only', or 'supervised'.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the routing decision between 0.0 and 1.0.",
    )
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of why this persona and autonomy were chosen.",
    )


class Persona(BaseModel):
    """Specification of an agent persona loaded from configuration."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(
        ...,
        description="Unique string identifier for the persona (e.g., 'coder', 'researcher').",
    )
    name: str = Field(
        ...,
        description="Human-friendly display name of the persona.",
    )
    description: str = Field(
        ...,
        description="Short description of the persona's role and specialties.",
    )
    system_prompt: str = Field(
        default="",
        description="Base system prompt instructing the LLM runtime when acting as this persona.",
    )
    allowed_tools: List[str] = Field(
        default_factory=list,
        description="Full catalog of tool names this persona is qualified to use.",
    )
    default_autonomy: str = Field(
        default="semi",
        description="Default autonomy level assigned to this persona unless overridden by router.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional configuration attributes (e.g., model preferences, temperature).",
    )


class ToolSpec(BaseModel):
    """Specification of a tool available in the tool registry."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(
        ...,
        description="Unique name of the tool, referenced by personas and route decisions.",
    )
    description: str = Field(
        ...,
        description="Clear description of the tool's behavior and intended usage.",
    )
    parameters_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema describing the required and optional input arguments.",
    )
    return_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema describing the output structure returned by the tool.",
    )
    required_scopes: List[str] = Field(
        default_factory=list,
        description="Security or capability scopes needed to authorize executing this tool.",
    )


class ActionRequest(BaseModel):
    """Proposed action invocation generated by a persona/runtime requesting tool execution."""

    model_config = ConfigDict(frozen=True)

    call_id: str = Field(
        ...,
        description="Unique invocation ID for this tool call event.",
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool requested to be run.",
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of input parameters supplied to the tool.",
    )
    caller_persona: str = Field(
        ...,
        description="Persona identifier that initiated the action request.",
    )
    risk_assessment: Optional[str] = Field(
        default=None,
        description="Initial risk score or classification label attached to this action.",
    )


class ApprovalRequest(BaseModel):
    """Request dispatched to the safety approval subsystem when an action requires authorization."""

    model_config = ConfigDict(frozen=True)

    request_id: str = Field(
        ...,
        description="Unique identifier for the approval workflow tracking this request.",
    )
    action: ActionRequest = Field(
        ...,
        description="The underlying tool action requiring human or policy approval.",
    )
    risk_level: str = Field(
        ...,
        description="Assessed risk level: 'low', 'medium', 'high', or 'critical'.",
    )
    reason: str = Field(
        ...,
        description="Explanation detailing why approval is required before execution.",
    )
    required_role: str = Field(
        default="user",
        description="Role required to approve the request (e.g., 'user', 'admin', 'operator').",
    )


class ApprovalResponse(BaseModel):
    """Outcome returned by the approval subsystem."""

    model_config = ConfigDict(frozen=True)

    request_id: str = Field(
        ...,
        description="Matches the request_id of the corresponding ApprovalRequest.",
    )
    approved: bool = Field(
        ...,
        description="Whether the requested action is approved (True) or rejected (False).",
    )
    approver_id: str = Field(
        ...,
        description="Identifier of the entity that decided the approval (user id or 'auto-policy').",
    )
    feedback: Optional[str] = Field(
        default=None,
        description="Optional feedback or rejection reason provided by the approver.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the approval decision was recorded.",
    )


class MemoryNode(BaseModel):
    """Discrete cross-surface memory item persisted to the memory store."""

    model_config = ConfigDict(frozen=True)

    node_id: str = Field(
        ...,
        description="Unique identifier for this memory node.",
    )
    user_id: str = Field(
        ...,
        description="Internal canonical user ID this memory pertains to.",
    )
    surface: str = Field(
        ...,
        description="Surface from which this memory originated (e.g., 'cli', 'slack').",
    )
    project_tag: Optional[str] = Field(
        default=None,
        description="Optional project, workspace, or repository tag categorizing the memory.",
    )
    persona: str = Field(
        ...,
        description="Persona that participated in or authored the remembered interaction.",
    )
    summary: str = Field(
        ...,
        description="Concise factual summary of the interaction or knowledge snippet.",
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Optional vector embedding representation of the summary for similarity search.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this memory entry was recorded.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional arbitrary metadata associated with this memory snippet.",
    )


class Response(BaseModel):
    """End-to-end response delivered back to the calling surface adapter.

    Includes the generated reply along with transparency metadata explaining
    the routing decision.
    """

    model_config = ConfigDict(frozen=True)

    reply_text: str = Field(
        ...,
        description="The primary textual response generated by the agent runtime.",
    )
    persona_used: str = Field(
        ...,
        description="The identifier of the persona that produced this response.",
    )
    route_decision: RouteDecision = Field(
        ...,
        description="The exact RouteDecision that guided execution for this turn.",
    )
    routing_explanation: str = Field(
        ...,
        description="Formatted transparency line, e.g. 'Summoned <persona> because ...'.",
    )
    session_id: str = Field(
        ...,
        description="The session ID associated with this turn.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the response was generated.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured response metadata (e.g. execution metrics, tokens).",
    )
