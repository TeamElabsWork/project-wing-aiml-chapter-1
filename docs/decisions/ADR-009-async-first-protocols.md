# ADR-009: Async-First Protocols for I/O Boundaries

## Status
Accepted

## Context
The Surface-Aware Agent Orchestration system coordinates interactions across multiple surfaces (CLI, Telegram, Slack, Web API). Several core components interact with external systems or incur significant latency:
1. LLM inference and structured completion generation.
2. Vector embeddings generation and database retrieval (PostgreSQL + pgvector).
3. Conversation session persistence (Redis / DB).
4. Human-in-the-loop approval workflows and interactive chat prompts.
5. Asynchronous tool execution (e.g., GitHub PR creation, external APIs).

Using synchronous protocols would block worker threads, cripple HTTP server concurrency, complicate Server-Sent Events (SSE) token streaming, and necessitate ad-hoc threadpool wrapping once real I/O is introduced.

Conversely, pure business and policy logic (such as surface constraint evaluation, risk tier classification, and routing explanation rendering) have no I/O requirements and should remain deterministic and synchronous.

## Decision
1. **Async-first I/O protocols**: Every Protocol method that performs I/O or calls latency-heavy backends is defined as `async def`:
   - `Router.route(...)`
   - `AgentRuntime.execute(...)` and `AgentRuntime.stream(...)`
   - `MemoryRepository.save(...)`, `search(...)`, `get_by_id(...)`, `list_all(...)`
   - `MemoryRetriever.retrieve(...)`
   - `MemoryWriter.write_interaction(...)`
   - `SessionManager.get_session(...)`, `update_session(...)`, `append_turn(...)`
   - `ApprovalManager.request_approval(...)`
   - `LLMProvider.complete(...)` and `LLMProvider.structured(...)`
   - `EmbeddingProvider.embed(...)`
   - `OrchestratorPipeline.process(...)` and `OrchestratorPipeline.stream(...)`

2. **Sync-only pure logic**: Pure, CPU-bound policy and formatting components remain strictly synchronous:
   - `SurfacePolicyProtocol.evaluate(...)`
   - `ToolScopeEnforcer.enforce(...)`
   - `RiskClassifier.classify(...)`
   - `RoutingLoggerProtocol.emit_log(...)` and `render_explanation(...)`

3. **Outer edge resolution**: Interactive synchronous interfaces (such as `CLIAdapter.run_repl`) bridge into the async pipeline using `asyncio.run(...)` at the outermost edge of execution.

## Consequences
- High concurrency and low latency across the FastAPI ingress service (`apps/api`).
- Seamless support for real-time SSE token streaming to clients.
- Clean separation of pure business logic from asynchronous execution.
- Eliminates technical debt when module owners replace day-1 stubs with live database and LLM integrations.
