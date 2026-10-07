# Guide: Adding or Implementing a Module

This repository is designed so that a team of 8 can work simultaneously without conflicts.
Follow these steps whenever you are replacing a stub with a real implementation or adding a new plugin.

---

## The Golden Rules

1. **Only import `contracts` directly**: Never import another module's concrete implementation. If you need functionality from another module, define or use a Python Protocol/interface.
2. **Never break existing contracts**: Do not alter field types or remove required fields in `packages/contracts`. Schema changes require consensus from dependent module owners (see `CODEOWNERS`).
3. **Register via Registries**: Register your implementation in the corresponding registry (`RouterRegistry`, `RuntimeRegistry`, `ToolRegistry`, etc.) and activate it via config (`config/*.yaml` or environment variables).

---

## Step-by-Step Walkthrough

### Example: Replacing the Mock Router (`B2`) with an LLM-based Router

#### Step 1: Work in your package
Go to `packages/routing/router/routing_router/`.
Create a new file, e.g., `llm_router.py`.

#### Step 2: Implement the Protocol
Your class must implement the `Router` protocol defined in `routing_router.base`:

```python
from contracts.models import RequestEnvelope, RouteDecision, MemoryNode
from routing_router.base import RouterRegistry
from typing import Dict, Any, List


class LLMRoutingEngine:
    def __init__(self, model_name: str = "claude-3-5-sonnet") -> None:
        self.model_name = model_name

    def route(
        self,
        envelope: RequestEnvelope,
        session_state: Dict[str, Any],
        surface_policy: Dict[str, Any],
        memory_context: List[MemoryNode],
    ) -> RouteDecision:
        # 1. Format prompt with surface_context, session, and memory
        # 2. Call your LLM backend
        # 3. Return the standard RouteDecision contract:
        return RouteDecision(
            persona="coder",
            tool_scope=["echo", "read_file"],
            autonomy="semi",
            confidence=0.98,
            reasoning="Task involves debugging Python code.",
        )


# Register your implementation
RouterRegistry.register("llm_router", lambda **kwargs: LLMRoutingEngine(**kwargs))
```

#### Step 3: Switch in Config
Update `config/models.yaml`:
```yaml
router:
  provider: "llm_router"
  model_name: "claude-3-5-sonnet"
```

#### Step 4: Write Unit Tests
Add your tests inside your package or in `tests/`. Verify that your router passes the evals harness:
```bash
python -m evals.runner
```

---

## Example: Adding a New Tool (`C4`)

1. Define a `ToolSpec` and handler function in `packages/personas/tools_impl/`:
   ```python
   from contracts.models import ToolSpec
   from personas_tools_core.registry import ToolRegistry

   MY_TOOL = ToolSpec(
       name="calculate_sum",
       description="Computes sum of numbers",
       parameters_schema={"type": "object", "properties": {"numbers": {"type": "array"}}},
   )


   def calculate_sum(numbers: list[float]) -> dict:
       return {"result": sum(numbers)}


   ToolRegistry.register(MY_TOOL, calculate_sum)
   ```
2. Whitelist the tool in any persona's `allowed_tools` list in `config/personas/*.yaml`.
3. The `ToolScopeEnforcer` will automatically validate tool calls during execution.
