# System Contracts Reference (v0.2.0)

This document catalogs every Pydantic contract located in `packages/contracts/contracts/models.py`, specifying its purpose, schema fields, producers, and consumers.

---

### 1. `RouteDecision` (Central Contract)
The central routing decision contract determining persona, capabilities, autonomy level, urgency, and justification.

| Field | Type | Description |
|---|---|---|
| `persona` | `str` | Chosen persona ID (`coder`, `researcher`, `ops`, `writer`). |
| `tool_scope` | `List[str]` | Whitelist of tools allowed to be called during this turn. |
| `autonomy` | `Autonomy` | Autonomy tier (`supervised`, `semi`, `full`, `read_only`). |
| `urgency` | `UrgencyLevel` | Urgency tier (`low`, `medium`, `high`, `critical`). |
| `confidence` | `float` | Router confidence score in range `[0.0, 1.0]`. |
| `reasoning` | `str` | Clear justification explaining why this route was selected. |

- **Producer**: Router (`B2`)
- **Consumers**: Persona Registry (`C1`), Agent Runtime (`C2`), Safety Subsystem (`D1`, `D2`), Routing Logger (`F1`).

---

### 2. `PolicyEvaluation`
Structured evaluation output from the Surface Policy Engine.

| Field | Type | Description |
|---|---|---|
| `is_urgent` | `bool` | Whether input text or surface cues signify urgent processing. |
| `urgency` | `UrgencyLevel` | Assessed urgency level (`low`, `medium`, `high`, `critical`). |
| `default_autonomy` | `Autonomy` | Baseline autonomy permitted by the surface policy. |
| `max_tokens_budget` | `int` | Maximum recommended token response length. |
| `supports_markdown` | `bool` | Whether markdown rendering is supported on this surface. |
| `extras` | `Dict[str, Any]` | Additional surface policy attributes. |

- **Producer**: Surface Policy Engine (`B1`)
- **Consumer**: Router (`B2`)

---

### 3. `SessionState`
Multi-turn conversation session state.

| Field | Type | Description |
|---|---|---|
| `session_id` | `str` | Unique session identifier. |
| `history` | `List[Dict[str, Any]]` | List of prior conversation turns. |
| `active_persona` | `Optional[str]` | Currently assigned sticky persona. |
| `metadata` | `Dict[str, Any]` | Arbitrary session state variables. |

- **Producer**: Session Manager (`B3`)
- **Consumers**: Router (`B2`), Agent Runtime (`C2`)

---

### 4. `RequestEnvelope`
Normalized cross-surface input event.

| Field | Type | Description |
|---|---|---|
| `message_id` | `str` | Unique message UUID. |
| `session_id` | `str` | Conversation session/thread identifier. |
| `user_id` | `str` | Internal canonical user ID. |
| `raw_text` | `str` | Unprocessed input text from the surface. |
| `surface_context` | `SurfaceContext` | Environmental metadata describing the source surface. |
| `metadata` | `Dict[str, Any]` | Extensible event metadata. |
| `timestamp` | `datetime` | UTC timestamp of event creation. |

- **Producer**: Gateway Normalizer (`A3`)
- **Consumers**: Router (`B2`), Agent Runtime (`C2`), Memory Writer (`E2`), Session Manager (`B3`).

---

### 5. `ToolSpec`
Formal catalog specification of an agent tool.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique tool name (`echo`, `github_pr`, `destructive_wipe`). |
| `description` | `str` | Natural language explanation of tool capability. |
| `parameters_schema` | `Dict[str, Any]` | JSON Schema for arguments. |
| `return_schema` | `Dict[str, Any]` | JSON Schema for return value. |
| `required_scopes` | `List[str]` | Required permissions/scopes. |
| `destructive` | `bool` | If True, tool always requires explicit approval across all surfaces. |
| `side_effects` | `SideEffects` | Side effect classification (`none`, `read`, `write`, `external`). |
| `execution_target` | `ExecutionTarget` | Target environment (`local`, `remote`, `browser`). |

- **Producers**: Tool Implementers (`C4`).
- **Consumers**: Tool Registry (`C3`), Tool Scope Enforcer (`C3`), Tool Executor (`C3`), Risk Classifier (`D1`).

---

### 6. `ToolCall` & `ToolResult`
Structured tool invocation and execution payloads.

- `ToolCall`: `call_id: str`, `tool_name: str`, `arguments: Dict[str, Any]`
- `ToolResult`:
  - `call_id: str`: Unique invocation identifier.
  - `tool_name: str`: Tool invoked.
  - `ok: bool`: True if tool executed successfully.
  - `output: Any`: Tool execution output data.
  - `error: Optional[str]`: Execution or rejection error message.
  - `denied: bool`: True if the call was explicitly rejected by human/policy approval.
  - `pending: bool`: True if the call requires human approval before proceeding.

---

### 7. `RuntimeResult`
Structured outcome produced by `AgentRuntime.execute(...)` replacing string inspection.

| Field | Type | Description |
|---|---|---|
| `reply_text` | `str` | Primary textual response for user rendering. |
| `tool_results` | `List[ToolResult]` | Structured outcomes of all tools invoked during the turn. |
| `pending_approval` | `Optional[ApprovalRequest]` | Populated if any tool requires human authorization. |
| `error` | `Optional[str]` | Runtime failure message if execution faulted. |

- **Producers**: `AgentRuntime` implementations (`EchoRuntime`, `ScriptedRuntime`, LLM runtimes).
- **Consumers**: `OrchestratorPipeline` (derives turn `status` strictly from `RuntimeResult`).

---

### 8. `Response`
End-to-end response delivered back to the calling surface adapter.

| Field | Type | Description |
|---|---|---|
| `reply_text` | `str` | The primary textual response generated by the agent runtime. |
| `persona_used` | `str` | Identifier of the persona that produced this response. |
| `route_decision` | `RouteDecision` | The exact RouteDecision that guided execution. |
| `routing_explanation` | `str` | Formatted transparency line (`Summoned <persona> because ...`). |
| `session_id` | `str` | The session ID associated with this turn. |
| `status` | `ResponseStatus` | Execution status: `complete`, `pending_approval`, `denied`, `error`. Derived purely from `RuntimeResult`. |
| `pending_approval` | `Optional[ApprovalRequest]` | If pending approval, the approval workflow request object. |
| `timestamp` | `datetime` | Timestamp when the response was generated. |
| `metadata` | `Dict[str, Any]` | Structured response metrics. |
