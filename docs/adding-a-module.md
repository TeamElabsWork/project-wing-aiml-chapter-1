# Guide: Adding or Implementing a Module

This repository is designed so that a team of 8 can work simultaneously without conflicts.
Follow these steps whenever you are replacing a stub with a real implementation or adding a new plugin.

---

## The Golden Rules

1. **Only import `contracts` directly**: Never import another module's concrete implementation. If you need functionality from another module, define or use a Python Protocol/interface.
2. **Never break existing contracts**: Do not alter field types or remove required fields in `packages/contracts`. Schema changes require consensus from dependent module owners (see `CODEOWNERS`).
3. **Async-first for I/O**: Protocol methods performing I/O, LLM generation, or database operations must be `async def` (see `ADR-009`). Pure policy evaluation remains sync.
4. **Register via Registries**: Register your implementation in the corresponding registry (`RouterRegistry`, `RuntimeRegistry`, `ToolRegistry`, `MemoryStoreRegistry`, etc.) and activate it via config (`config/pipeline.yaml`, `config/models.yaml`).

---

## Step-by-Step Walkthrough

### Example: Implementing a Real LLM-based Router (`B2`)

#### Step 1: Work in your package
Go to `packages/routing/router/routing_router/`.
Create a new file, e.g., `llm_router.py`.

#### Step 2: Implement the Async Protocol
Your class must implement the `Router` protocol defined in `routing_router.base`:

```python
from contracts.models import (
    MemoryNode,
    PolicyEvaluation,
    RequestEnvelope,
    RouteDecision,
    SessionState,
)
from routing_router.base import RouterRegistry
from typing import List


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

#### Step 4: Validate
Run the test suite and evaluation harness:
```bash
make test
make evals
```
