# ADR-010: Deferred Tool Execution on Approval

## Status
Accepted

## Context
When an agent attempts a sensitive or high-risk tool call (e.g., destructive actions or infrastructure changes), the execution must be paused awaiting human review. The orchestrator must not execute the action immediately; instead, it generates an `ApprovalRequest` with a unique `request_id`, marks the tool result and turn status as `pending_approval`, and returns control to the client/surface.

Once a human or policy submits an approval decision (via `/approve <id>` in the CLI, or `POST /v1/approvals/{request_id}` in the API), the system must resume or execute the pending tool call.

## Decision
1. **Request and Action Storing**:
   In `PendingApprovalManager`, each approval request stores the associated `ActionRequest` (including `call_id`, `tool_name`, and `arguments`).
2. **Execution upon Approval**:
   Upon receiving `submit_decision(request_id, ApprovalResponse(approved=True))`:
   - If `approved=True`, `PendingApprovalManager` dynamically looks up the tool in `ToolRegistry` and executes it with the stored arguments.
   - The result is stored as a `ToolResult` in `PendingApprovalManager.execution_results[request_id]`.
   - If `approved=False`, the request is marked denied without executing the tool.
3. **Status Derivation**:
   Pipeline turns derive their status strictly from `RuntimeResult`:
   - Status is `pending_approval` when `runtime_result.pending_approval` or any pending tool result is present.
   - Status is `denied` if any tool call is denied.
   - Status is `complete` when all operations complete successfully.

## Consequences
- Provides a deterministic, testable, and secure flow for gating and deferred tool execution.
- Gated operations can be approved and executed through any surface (CLI commands, API webhooks, Slack actions).
- Avoids re-prompting or duplicate LLM inference calls merely to rerun an already-approved action.
