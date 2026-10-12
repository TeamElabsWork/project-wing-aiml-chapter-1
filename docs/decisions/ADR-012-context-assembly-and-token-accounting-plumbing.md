# ADR-012: Context Assembly and Token Accounting Plumbing

## Status
Accepted

## Context
Earlier scaffolding routed requests based on surface policy, multi-turn session history, and cross-surface episodic memory. However, critical plumbing gaps remained:
1. **Disconnected Context & Budgets**: The surface token budget (`PolicyEvaluation.max_tokens_budget`) and retrieved cross-surface memory nodes reached the router only; `AgentRuntime.execute()` received neither.
2. **Untrimmed Session History**: Raw session history was passed whole to the runtime with no architectural boundary or interceptor to apply token budgeting, sliding windows, or summarization.
3. **Hardcoded Memory Retrieval Limit**: The number of cross-surface memory items retrieved was hardcoded to 3 in `pipeline.process()`.
4. **Missing Token Accounting**: Token usage was unrecorded across the system, making efficiency, cost, and surface budget compliance impossible to measure.
5. **Untyped LLM Provider Generation**: `LLMProvider.complete()` and `LLMProvider.structured()` returned plain strings and dictionaries without token usage metadata.

## Decision
1. **Introduce `ContextBuilder` Protocol and `ContextBundle` Contract**:
   - Placed a dedicated context assembly step between routing/persona lookup and runtime execution.
   - Defined `ContextBundle` containing `persona_prompt`, `history`, `memory`, `tool_specs` (filtered strictly to `decision.tool_scope`), `token_budget`, `estimated_tokens`, `dropped_items`, and `notes`.
   - Built `PassthroughContextBuilder` as the default backend registered in `ContextBuilderRegistry`. It serves as a deliberate no-op stub that preserves full history and retrieved memory while enforcing tool whitelisting and calculating crude estimated tokens (`len(text) // 4`).
2. **Introduce `TokenUsage` and `LLMResponse` Contracts**:
   - Added `TokenUsage {prompt_tokens, completion_tokens, total_tokens, estimated}` to `contracts/models.py`.
   - Introduced `LLMResponse {text, parsed, usage}` as the typed return wrapper for `LLMProvider.complete()` and `structured()`. Updated `MockLLMProvider` accordingly.
   - Added `usage: TokenUsage` (default zeros) to `RuntimeResult` and `Response`.
3. **Update `AgentRuntime` Protocol and Stub Implementations**:
   - `AgentRuntime.execute()` and `.stream()` gain `context: Optional[ContextBundle] = None`. Raw `session_history` is retained but marked deprecated.
   - `EchoRuntime` and `ScriptedRuntime` accept `context` and return `RuntimeResult.usage` populated with `len//4` token estimates. `EchoRuntime` displays context size, memory node count, and token budget in its formatted acknowledgment.
4. **Configurable Memory Retrieval Limit**:
   - Added `limits.memory_retrieval_limit` (default 3) to `config/pipeline.yaml`. `create_pipeline()` injects this limit into `OrchestratorPipeline`.
5. **Structured Routing Log Line Enrichment**:
   - Enriched routing transparency logs to emit `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_tokens`, and `dropped_items`.
6. **Token Reporting in Evaluation Harness**:
   - Extended `evals/runner.py` to calculate and report estimated tokens per benchmark case and in aggregate across the evaluation suite without enforcing artificial pass/fail thresholds.

## Deliberately Deferred (Future Implementation)
The following capabilities are explicitly deferred behind the established interfaces:
- Real history windowing, sliding buffers, and message trimming.
- Multi-turn conversation summarization and LLM fact extractors.
- Memory relevance re-ranking and vector distance thresholding.
- Repository context retrieval tools.
- Prompt caching headers and cache hit token accounting.
- Pass/fail token budget and monetary cost target thresholds in `evals/runner.py`.

## Consequences
- The agent runtime now has full access to surface-specific token budgets, allowed tools, and cross-surface episodic memory.
- Token consumption is tracked from LLM generation up to surface responses and transparency logs.
- Clear module ownership: C2 (Runtime) and E3 (Memory) can implement real trimming and memory ranking inside `personas_context_builder` without altering pipeline wiring or contracts.
