# Surface-Aware Agent Orchestration

An agent orchestration layer where routing depends on the task text **AND** the surface the request came from (CLI, Telegram, Slack, Web), session state, and a shared cross-surface episodic memory.

Built as an open-ended, modular monorepo scaffold designed for a team of 8 engineers working in parallel without stepping on each other.

---

## Quickstart & Demos

### 1. Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### 2. Setup
Install all workspace packages and development dependencies in editable mode:
```bash
uv sync --all-packages
# or if make is installed:
make setup
```

### 3. Run the Demos

#### Demo 1: Default Interactive CLI Demo (Echo Runtime)
Launch the standard CLI demo REPL:
```bash
make demo
# or: uv run python -m orchestrator.cli_entry
```
- Typing any message flows through: `Gateway` -> `Identity` -> `Surface Policy` -> `Router (Mock)` -> `Persona` -> `Runtime (Echo)` -> `Memory Persistence (Stub)` -> `Formatted Reply`.
- Every reply includes the mandatory routing explanation line:
  ```
  [ROUTING] Summoned coder because Selected 'coder' on surface 'cli' (urgency: low). (autonomy: semi, confidence: 0.95)
  ```

#### Demo 2: Safety & Approval Workflow Demo (Scripted Runtime)
Launch the safety approval demo REPL:
```bash
make demo-safety
# or: uv run python -m orchestrator.cli_entry --safety
```
- Demonstrates human-in-the-loop safety gating with deferred tool execution.
- Type `wipe the cache` or `delete database`:
  - Risk classifier detects destructive intent.
  - Returns `[STATUS]: pending_approval` and displays `[PENDING APPROVAL REQUIRED]` with a unique Request ID.
- Type `/approve <id>` to authorize:
  - Executes the pending tool call and displays `[TOOL EXECUTED]`.
- Type `/deny <id>` to reject:
  - Rejection is recorded and marked denied.

### 4. Run the API Ingress Server
Start the FastAPI ingress service:
```bash
uv run uvicorn api.main:app --reload --port 8000
# or:
make api
```
Verify the healthcheck:
```bash
curl http://localhost:8000/healthz
# {"status":"ok","version":"0.2.0"}
```

### 5. Run Database Migrations
```bash
# Substitute configured embedding dimensions into initial schema
make migrate
```

### 6. Run Tests, Linting & Evals
```bash
# Run full pytest suite (smoke tests, async safety, contracts, and evals)
make test

# Run linting and type-checking
make lint

# Run the routing evaluation benchmark harness
make evals
```

---

## Repository Map & Module Breakdown

```text
/packages
  /contracts            shared Pydantic schemas v0.2.0 (the ONLY thing every module may import)
  /surfaces
    /telegram_slack     A1  chat adapter (stub)
    /cli                A2  CLI adapter (working REPL with /approve and /deny commands)
  /gateway              A3  event normalizer: raw surface input -> RequestEnvelope
  /identity             A4  resolve_user(surface, external_id) (in-memory/config-file stub)
  /routing
    /surface_policy     B1  surface profiles + urgency rules (PolicyEvaluation)
    /router             B2  async Router interface + MockRouter
    /session            B3  async session state manager (SessionState)
  /personas
    /registry           C1  loads persona YAML files; includes 4 personas (coder, researcher, ops, writer)
    /runtime            C2  async agent runtime interface + EchoRuntime + ScriptedRuntime + MockLLMProvider
    /tools_core         C3  ToolSpec, ToolRegistry, ToolScopeEnforcer, ToolExecutor with safety gating
    /tools_impl         C4  example tools: echo, github_pr (remote), destructive_wipe (destructive)
  /safety
    /risk_classifier    D1  RiskClassifier protocol + ToolSpec risk inspection
    /approval           D2  async ApprovalManager protocol + AutoApproveStub + DenyAllApprovalStub + PendingApprovalManager
  /memory
    /store              E1  schema + migrations + async MemoryRepository + EmbeddingProvider
    /writer             E2  async MemoryWriter interface + stub
    /retriever          E3  async MemoryRetriever interface + stub
  /transparency
    /routing_log        F1  renders "Summoned <persona> because ..." + structured log
/apps
  /orchestrator         wires everything together asynchronously; pipeline factory from config
  /api                  FastAPI ingress with /healthz, /v1/message, /v1/stream (SSE), webhooks, and IdempotencyStore
/evals                  F2  routing benchmark harness: cases.yaml + async runner
/infra                  F3  docker-compose.yml (postgres+pgvector reference), Dockerfile, .env.example
/config                 surfaces.yaml, personas/*.yaml, models.yaml, pipeline.yaml
/docs                   architecture.md, contracts.md, adding-a-module.md, decisions/ (ADRs 001-011)
CODEOWNERS, Makefile, pyproject.toml (workspace), .pre-commit-config.yaml, README.md
```

---

## Core Architecture Principles

1. **Contracts First**: All shared types live in `packages/contracts/`. Modules depend **only** on `/contracts` and on interfaces (Python `Protocol`s), never on another module's concrete implementation.
2. **Async-First Protocols**: All I/O-bound protocol methods (Router, Runtime, Memory, Session, Approval, Pipeline) are `async def` (ADR-009). Pure evaluation logic (SurfacePolicy, ToolScopeEnforcer, RiskClassifier) remains synchronous.
3. **Pluggable Registries**: Adapters, tools, personas, router engines, runtimes, memory stores, and approval managers register themselves into lightweight registries (`RouterRegistry`, `RuntimeRegistry`, `ToolRegistry`, `MemoryStoreRegistry`, `ApprovalManagerRegistry`) and are selected via `config/pipeline.yaml` and `config/models.yaml`.
4. **Safety Gating & Deferred Execution**: Destructive actions (`ToolSpec.destructive = True`) unconditionally require explicit approval across all surfaces. Gated calls pause with `pending_approval` until reviewed via CLI or API (ADR-010).
5. **Vendor Agnostic**: Zero hardcoded vendor SDK dependencies. The LLM and embedding provider protocols ship with deterministic mock providers, leaving model slots configured as `unset` in `config/models.yaml`.
6. **Day-1 Execution Without Docker**: The default setup runs entirely in-memory using pure Python. Postgres + pgvector migrations and Docker definitions are provided in `/infra` for future deployment (ADR-011).

---

## Development & Contributing Documentation

- [Contributing Guidelines](CONTRIBUTING.md) — Issue difficulty tiers, branch standards, and PR checklist
- [Architecture Overview](docs/architecture.md) — System flow, request lifecycle, and component interaction
- [Contracts Reference](docs/contracts.md) — Detailed schema reference for every Pydantic contract
- [How to Add or Implement a Module](docs/adding-a-module.md) — Guide for building behind interfaces
- [Architecture Decision Records (ADRs)](docs/decisions/):
  - [ADR-001: Central Contracts Package](docs/decisions/ADR-001-contracts-package.md)
  - [ADR-002: In-Memory Component Registries](docs/decisions/ADR-002-pluggable-registry-pattern.md)
  - [ADR-003: Vendor-Agnostic LLM Provider Protocol](docs/decisions/ADR-003-llm-provider-abstraction.md)
  - [ADR-004: Dual In-Memory and pgvector Memory Backend](docs/decisions/ADR-004-memory-and-pgvector-schema.md)
  - [ADR-005: Gateway Normalization & Surface Context](docs/decisions/ADR-005-surface-normalization.md)
  - [ADR-006: Code Execution Model & Remote Actions (GitHub PRs vs Local CLI)](docs/decisions/ADR-006-execution-model-and-remote-actions.md)
  - [ADR-007: PostgreSQL + pgvector for Unified Memory Storage](docs/decisions/ADR-007-postgres-pgvector-for-memory-storage.md)
  - [ADR-008: Production Hosting & Process Lifecycle Management](docs/decisions/ADR-008-hosting-and-production-lifecycle.md)
  - [ADR-009: Async-First Protocols for I/O Boundaries](docs/decisions/ADR-009-async-first-protocols.md)
  - [ADR-010: Deferred Tool Execution on Approval](docs/decisions/ADR-010-deferred-tool-execution-on-approval.md)
  - [ADR-011: Unified Memory Schema and Dynamic Vector Dimensions](docs/decisions/ADR-011-unified-memory-schema-and-dynamic-vector-dimensions.md)
