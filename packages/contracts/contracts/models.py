"""Shared Pydantic contracts for Surface-Aware Agent Orchestration.

These schemas are the single source of truth across all modules in the repository.
Every module may import contracts; no module may import another module's internal implementation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Core Literal & Enum domain types
Autonomy = Literal["full", "semi", "read_only", "supervised"]
RiskLevel = Literal["low", "medium", "high", "critical"]
UrgencyLevel = Literal["low", "normal", "high"]
SideEffects = Literal["none", "read", "write", "external"]
ExecutionTarget = Literal["local", "remote", "any"]
ResponseStatus = Literal["complete", "pending_approval", "denied", "error"]

SurfaceType = str
KNOWN_SURFACES: Set[str] = {"cli", "telegram", "slack", "web"}


class SurfaceContext(BaseModel):
    """Contextual metadata describing the surface from which an event originated.

    Different surfaces (CLI, Telegram, Slack, Web, etc.) impose different
    interaction constraints, urgency assumptions, and output capabilities.
    """

    model_config = ConfigDict(frozen=True)

    surface_type: SurfaceType = Field(
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
    urgency_hint: Optional[UrgencyLevel] = Field(
        default=None,
        description="Urgency hint inferred from the surface or client payload ('low', 'normal', 'high').",
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


class PolicyEvaluation(BaseModel):
    """Structured outcome of surface policy evaluation."""

    model_config = ConfigDict(frozen=True)

    is_urgent: bool = Field(
        default=False,
        description="Whether the request is classified as urgent.",
    )
    urgency: UrgencyLevel = Field(
        default="normal",
        description="Urgency tier ('low', 'normal', 'high').",
    )
    default_autonomy: Autonomy = Field(
        default="semi",
        description="Default autonomy mode prescribed by the surface policy.",
    )
    max_tokens_budget: int = Field(
        default=2048,
        description="Maximum token budget recommended for the response on this surface.",
    )
    supports_markdown: bool = Field(
        default=True,
        description="Whether the active surface can render markdown.",
    )
    extras: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional policy evaluation attributes.",
    )


class SessionState(BaseModel):
    """Structured representation of active multi-turn conversation session state."""

    model_config = ConfigDict(frozen=True)

    session_id: str = Field(
        ...,
        description="Unique session identifier.",
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of prior interaction turns in chronological order.",
    )
    active_persona: Optional[str] = Field(
        default=None,
        description="Persona identifier currently active or most recently summoned.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary session metadata (e.g. created_at, user context).",
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
    autonomy: Autonomy = Field(
        default="semi",
        description="Autonomy mode granted: 'full', 'semi', 'read_only', or 'supervised'.",
    )
    urgency: UrgencyLevel = Field(
        default="normal",
        description="Urgency classification for this routing decision ('low', 'normal', 'high').",
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
    default_autonomy: Autonomy = Field(
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
    destructive: bool = Field(
        default=False,
        description="Whether this tool performs irreversible or destructive mutations.",
    )
    side_effects: SideEffects = Field(
        default="none",
        description="Nature of side effects caused by this tool: 'none', 'read', 'write', 'external'.",
    )
    execution_target: ExecutionTarget = Field(
        default="any",
        description="Where this tool must run: 'local' (developer client), 'remote' (server/cloud), 'any'.",
    )


class ToolCall(BaseModel):
    """Proposed tool call invocation emitted by an agent runtime."""

    model_config = ConfigDict(frozen=True)

    call_id: str = Field(
        ...,
        description="Unique call invocation ID.",
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool to invoke.",
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments passed to the tool.",
    )


class ToolResult(BaseModel):
    """Result returned after a tool execution."""

    model_config = ConfigDict(frozen=True)

    call_id: str = Field(
        ...,
        description="Matches the call_id of the ToolCall.",
    )
    tool_name: str = Field(
        ...,
        description="Name of the invoked tool.",
    )
    ok: bool = Field(
        ...,
        description="Whether execution completed successfully.",
    )
    output: Any = Field(
        default=None,
        description="Output payload returned by the tool.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error description if execution failed or was denied.",
    )
    denied: bool = Field(
        default=False,
        description="Whether this tool execution was explicitly denied by approval or policy.",
    )
    pending: bool = Field(
        default=False,
        description="Whether this tool execution is waiting on approval before proceeding.",
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
    risk_assessment: Optional[RiskLevel] = Field(
        default=None,
        description="Assessed risk tier attached to this action ('low', 'medium', 'high', 'critical').",
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
    risk_level: RiskLevel = Field(
        default="medium",
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
        default="",
        description="Matches the request_id of the corresponding ApprovalRequest.",
    )
    approved: bool = Field(
        ...,
        description="Whether the requested action is approved (True) or rejected (False).",
    )
    approver_id: str = Field(
        default="operator",
        description="Identifier of the entity that decided the approval (user id or 'auto-policy').",
    )
    approver: Optional[str] = Field(
        default=None,
        description="Optional alias for approver_id.",
    )
    feedback: Optional[str] = Field(
        default=None,
        description="Optional feedback or rejection reason provided by the approver.",
    )
    pending: bool = Field(
        default=False,
        description="Whether the approval request remains pending awaiting decision.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the approval decision was recorded.",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_approver_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "approver" in data and "approver_id" not in data:
                data["approver_id"] = data["approver"]
            elif "approver_id" in data and "approver" not in data:
                data["approver"] = data["approver_id"]
        return data


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
    surface: SurfaceType = Field(
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


class TokenUsage(BaseModel):
    """Token consumption accounting for LLM prompts and completions."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = Field(
        default=0,
        description="Tokens consumed by the input prompt.",
    )
    completion_tokens: int = Field(
        default=0,
        description="Tokens generated in the completion.",
    )
    total_tokens: int = Field(
        default=0,
        description="Total tokens consumed (prompt + completion).",
    )
    estimated: bool = Field(
        default=True,
        description="Whether counts are estimated (len//4) or reported by provider.",
    )

    @model_validator(mode="before")
    @classmethod
    def calculate_total_tokens(cls, data: Any) -> Any:
        if isinstance(data, dict):
            prompt = data.get("prompt_tokens", 0) or 0
            completion = data.get("completion_tokens", 0) or 0
            if (
                "total_tokens" not in data
                or data.get("total_tokens") is None
                or data.get("total_tokens") == 0
            ):
                data["total_tokens"] = prompt + completion
        return data


class ContextBundle(BaseModel):
    """Assembled persona prompt, session history, memory, and tool context for agent execution."""

    model_config = ConfigDict(frozen=True)

    persona_prompt: str = Field(
        ...,
        description="Base persona system prompt instructions.",
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Session history turns prepared for the runtime.",
    )
    memory: List[MemoryNode] = Field(
        default_factory=list,
        description="Retrieved cross-surface memory items.",
    )
    tool_specs: List[ToolSpec] = Field(
        default_factory=list,
        description="Specifications for tools permitted by the route decision.",
    )
    token_budget: int = Field(
        ...,
        description="Maximum token budget allocated for this execution turn.",
    )
    estimated_tokens: int = Field(
        default=0,
        description="Crude token count estimation for the assembled context.",
    )
    dropped_items: int = Field(
        default=0,
        description="Count of history or memory items dropped due to budget constraints.",
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Informational notes or assembly logs.",
    )


class LLMResponse(BaseModel):
    """Response returned by an LLM provider completion or structured generation call."""

    model_config = ConfigDict(frozen=True)

    text: Optional[str] = Field(
        default=None,
        description="Text generated by the LLM provider.",
    )
    parsed: Optional[Any] = Field(
        default=None,
        description="Parsed structured output payload conforming to requested schema.",
    )
    usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Token usage statistics for this LLM invocation.",
    )

    @model_validator(mode="before")
    @classmethod
    def handle_payload_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "payload" in data:
                payload_val = data.pop("payload")
                if "parsed" not in data or data.get("parsed") is None:
                    data["parsed"] = payload_val
                if "text" not in data or data.get("text") is None:
                    if isinstance(payload_val, str):
                        data["text"] = payload_val
        return data

    @property
    def payload(self) -> Any:
        """Convenience property returning parsed payload if present, else text."""
        return self.parsed if self.parsed is not None else self.text


class RuntimeResult(BaseModel):
    """Structured result returned by AgentRuntime execution."""

    model_config = ConfigDict(frozen=True)

    reply_text: str = Field(
        ...,
        description="Textual reply generated by the persona / agent loop.",
    )
    tool_results: List[ToolResult] = Field(
        default_factory=list,
        description="List of tool invocations executed or attempted during this turn.",
    )
    pending_approval: Optional[ApprovalRequest] = Field(
        default=None,
        description="Populated if execution was halted awaiting human or policy approval.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Runtime execution error description if turn encountered an unhandled fault.",
    )
    usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Token usage statistics for this runtime execution turn.",
    )


class Response(BaseModel):
    """End-to-end response delivered back to the calling surface adapter.

    Includes the generated reply along with transparency metadata explaining
    the routing decision, execution status, and any pending approval requests.
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
    status: ResponseStatus = Field(
        default="complete",
        description="Overall execution status: 'complete', 'pending_approval', 'denied', 'error'.",
    )
    pending_approval: Optional[ApprovalRequest] = Field(
        default=None,
        description="If status is 'pending_approval', the approval request requiring action.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the response was generated.",
    )
    usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Token usage statistics for the overall execution turn.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured response metadata (e.g. execution metrics, tokens).",
    )
