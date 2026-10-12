# Guide: Adding or Implementing a Module

This repository is designed so that a team of 8 can work simultaneously without conflicts.
Follow these steps whenever you are replacing a stub with a real implementation or adding a new plugin.

---

## The Golden Rules

1. **Only import `contracts` directly**: Never import another module's concrete implementation. If you need functionality from another module, define or use a Python Protocol/interface.
2. **Never break existing contracts**: Do not alter field types or remove required fields in `packages/contracts`. Schema changes require consensus from dependent module owners (see `CODEOWNERS`).
3. **Async-first for I/O**: Protocol methods performing I/O, LLM generation, or database operations must be `async def` (see `ADR-009`). Pure policy evaluation remains sync.
4. **Structured Runtime Execution**: `AgentRuntime.execute(...)` receives `context: Optional[ContextBundle]` and must return `RuntimeResult` with `reply_text`, `tool_results`, optional `pending_approval`, `usage: TokenUsage`, and `error`. The pipeline derives turn status (`complete`, `pending_approval`, `denied`, `error`) strictly from this contract.
5. **Approval Workflow Compatibility**: High-risk or destructive tools must participate in `ApprovalManager`. When an action requires human review, return `pending=True` in `ToolResult` and store the pending action in `PendingApprovalManager`. Execution is resumed upon `submit_decision(..., approved=True)` (see `ADR-010`).
6. **Register via Registries**: Register your implementation in the corresponding registry (`RouterRegistry`, `RuntimeRegistry`, `ContextBuilderRegistry`, `ToolRegistry`, `MemoryStoreRegistry`, etc.) and activate it via config (`config/pipeline.yaml`, `config/models.yaml`). Avoid side-effect registration on module import; register via factory functions or `register_defaults()`.

---

## Step-by-Step Walkthrough

### Example 1: Implementing a Real LLM-based Router (`B2`)

#### Step 1: Work in your package
Go to `packages/routing/router/routing_router/`.
Create a new file, e.g., `llm_router.py`.

#### Step 2: Implement the Async Protocol
Your class must implement the `Router` protocol defined in `routing_router.base`:

```python
from typing import List
from contracts.models import (
    MemoryNode,
    PolicyEvaluation,
    RequestEnvelope,
    RouteDecision,
    SessionState,
)
from routing_router.base import RouterRegistry


class LLMRoutingEngine:
    def __init__(self, model_name: str = "claude-3-5-sonnet") -> None:
        self.model_name = model_name

    async def route(
        self,
        envelope: RequestEnvelope,
        session_state: SessionState,
        surface_policy: PolicyEvaluation,
        memory_context: List[MemoryNode],
    ) -> RouteDecision:
        # 1. Format prompt with surface_context, session, and memory
        # 2. Call your async LLM provider (or mock provider)
        # 3. Return the standard RouteDecision contract:
        return RouteDecision(
            persona="coder",
            tool_scope=["echo", "read_file"],
            autonomy="semi",
            urgency=surface_policy.urgency,
            confidence=0.95,
            reasoning="Query asks for code implementation.",
        )


# Register your engine in the registry:
RouterRegistry.register("llm", lambda **kwargs: LLMRoutingEngine(**kwargs))
```

#### Step 3: Switch the configuration
In `config/pipeline.yaml`:
```yaml
backends:
  router: "llm"
```

---

### Example 2: Implementing a Custom ContextBuilder (`C2` / `E3`)

```python
from typing import Any, List
from contracts.models import (
    ContextBundle,
    MemoryNode,
    Persona,
    PolicyEvaluation,
    RequestEnvelope,
    RouteDecision,
    SessionState,
)
from personas_context_builder.base import ContextBuilderRegistry


class TrimmingContextBuilder:
    async def build(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        policy: PolicyEvaluation,
        session_state: SessionState,
        memory: List[MemoryNode],
        **kwargs: Any,
    ) -> ContextBundle:
        # 1. Trim history to last 5 turns or fit policy.max_tokens_budget
        trimmed_history = session_state.history[-5:]
        # 2. Re-rank and take top relevant memory nodes
        ranked_memory = memory[:3]
        # 3. Filter tool specs strictly to decision.tool_scope
        # 4. Return ContextBundle:
        return ContextBundle(
            persona_prompt=persona.system_prompt,
            history=trimmed_history,
            memory=ranked_memory,
            tool_specs=[],
            token_budget=policy.max_tokens_budget,
            estimated_tokens=len(persona.system_prompt) // 4,
            dropped_items=max(0, len(session_state.history) - len(trimmed_history)),
        )


ContextBuilderRegistry.register("trimming", lambda **kwargs: TrimmingContextBuilder())
```

In `config/pipeline.yaml`:
```yaml
backends:
  context_builder: "trimming"
```

---

### Example 3: Implementing a Custom Agent Runtime (`C2`)

```python
from typing import Any, Dict, List, Optional
from contracts.models import (
    ContextBundle,
    Persona,
    RequestEnvelope,
    RouteDecision,
    RuntimeResult,
    TokenUsage,
)
from personas_runtime.base import RuntimeRegistry


class CustomAgentRuntime:
    async def execute(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        context: Optional[ContextBundle] = None,
        **kwargs: Any,
    ) -> RuntimeResult:
        # 1. Extract context instructions and memory from ContextBundle
        budget = context.token_budget if context else 2048
        # 2. Perform reasoning loop respecting budget and permitted tools
        # 3. Return structured RuntimeResult with token usage:
        return RuntimeResult(
            reply_text="Execution complete.",
            tool_results=[],
            pending_approval=None,
            error=None,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=25, total_tokens=125),
        )


RuntimeRegistry.register("custom", lambda **kwargs: CustomAgentRuntime())
```

---

### Step 4: Validate
Run the test suite, linter, and evaluation harness:
```bash
make test
make lint
make evals
```
