# Architecture Overview: Surface-Aware Agent Orchestration

## 1. Core Problem
Traditional multi-agent systems treat input prompts identically regardless of whether they arrive from an IDE terminal, a Slack thread, a Telegram bot, or a web dashboard. 

**Surface-Aware Agent Orchestration** incorporates the origin surface, its operational affordances, urgency cues, multi-turn session state, and shared cross-surface episodic memory into every routing and execution decision.

```mermaid
flowchart TD
    RawSurface[Raw Surface Input: CLI / Slack / Telegram / API] --> A3[Gateway Normalizer]
    A3 --> A4[Identity Resolver]
    A4 --> Envelope[RequestEnvelope]
    Envelope --> B1[Surface Policy Engine]
    Envelope --> B3[Session Manager]
    Envelope --> E3[Memory Retriever]
    B1 --> B2[Router]
    B3 --> B2
    E3 --> B2
    B2 --> RouteDecision[RouteDecision]
    RouteDecision --> C1[Persona Registry]
    RouteDecision --> CB[Context Builder: C2 + E3]
    C1 --> CB
    B1 --> CB
    B3 --> CB
    E3 --> CB
    CB --> ContextBundle[ContextBundle: prompt, history, memory, tool_specs, budget]
    ContextBundle --> C2[Agent Runtime]
    C2 --> C3[Tool Executor & Enforcer]
    C3 --> D1[Safety Risk Classifier]
    D1 --> D2[Approval Manager]
    D2 --> C4[Tool Execution / Pending Gating]
    C2 --> RuntimeResult[RuntimeResult: reply_text, tool_results, pending_approval, usage]
    RuntimeResult --> StatusDerivation[Status Derivation: complete | pending_approval | denied | error]
    RuntimeResult --> E2[Memory Writer]
    E2 --> E1[Memory Store Repo]
    RouteDecision --> F1[Routing Logger]
    StatusDerivation --> Response[Response with Routing Explanation, Status & TokenUsage]
```

## 2. Request Lifecycle Step-by-Step

1. **Surface Ingestion**: An incoming message or webhook event is received by a surface adapter (`A1` Telegram/Slack, `A2` CLI, `apps/api` FastAPI gateway with idempotency deduplication).
2. **Event Normalization (`A3`) & Identity (`A4`)**: The Gateway packages raw input into a canonical `RequestEnvelope`, resolving external IDs (e.g. Telegram chat IDs) to internal `user_id` values via `IdentityResolverRegistry`.
3. **Surface Policy Evaluation (`B1`)**: Evaluates `surfaces.yaml` via `SurfacePolicyRegistry` to detect urgency keywords, token budgets, and default autonomy constraints.
4. **Context Gathering (`B3`, `E3`)**: Pulls active conversation history from `SessionManager` and relevant cross-surface memories from `MemoryRetriever` honoring configurable retrieval limits (`limits.memory_retrieval_limit` in `pipeline.yaml`).
5. **Route Decision Synthesis (`B2`)**: The Router produces a `RouteDecision` containing:
   - `persona`: The assigned agent specialist (`coder`, `researcher`, `ops`, `writer`).
   - `tool_scope`: Whitelist of permitted tools.
   - `autonomy`: Level of operational autonomy (`supervised`, `semi`, `full`).
   - `confidence`: Confidence score (0.0 to 1.0).
   - `reasoning`: Natural-language justification.
6. **Context Assembly (`ContextBuilder`, C2 / E3)**:
   - Retrieves the selected Persona definition (`C1`).
   - The `ContextBuilder` (`PassthroughContextBuilder` or custom strategy) compiles the `ContextBundle`.
   - Attaches the persona prompt, session history, retrieved episodic memories, tools allowed by `decision.tool_scope`, surface token budget (`PolicyEvaluation.max_tokens_budget`), and estimated token counts (ADR-012).
7. **Execution & Safety Gating (`C2`, `C3`, `D1`, `D2`)**:
   - The `AgentRuntime` executes reasoning loops using `ToolExecutor` and the compiled `ContextBundle`.
   - Tool calls pass through `ToolScopeEnforcer` and `RiskClassifier`.
   - High-risk or destructive tools trigger `ApprovalManager.request_approval(...)`. Under `PendingApprovalManager`, sensitive operations are paused with a pending `ApprovalRequest`.
   - The runtime returns a structured `RuntimeResult` containing `tool_results`, optional `pending_approval`, `usage: TokenUsage`, and `reply_text`.
8. **Status Derivation & Transparency Logging**:
   - `OrchestratorPipeline` derives `Response.status` strictly from `RuntimeResult`: `pending_approval` if pending authorization, `denied` if rejected, `error` if runtime fault, else `complete`.
   - `RoutingLogger` (`F1`) emits structured logs including token consumption metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_tokens`, `dropped_items`).
9. **Deferred Tool Execution on Approval**:
   - When a human issues `/approve <id>` in the CLI or `POST /v1/approvals/{request_id}` in the API, `ApprovalManager.submit_decision(...)` executes the deferred tool call and captures output.
10. **Cross-Surface Memory Persistence (`E2`, `E1`)**: Interaction facts, summaries, and embeddings are persisted to the repository.
11. **Response Delivery (`Response`)**: Delivers the final `Response` payload containing `reply_text`, `status`, `routing_explanation`, and `usage` back to the surface adapter.

## 3. Pluggable Extension Model
Every component is registered via in-memory factories and registries (`RouterRegistry`, `RuntimeRegistry`, `ContextBuilderRegistry`, `ToolRegistry`, `ApprovalManagerRegistry`, `MemoryStoreRegistry`, etc.), with clear configuration precedence: `pipeline.yaml` (if set) -> `models.yaml` (if set) -> `"default"`.
