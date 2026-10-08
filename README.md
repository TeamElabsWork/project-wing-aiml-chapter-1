# Surface-Aware Agent Orchestration

An agent orchestration layer where routing depends on the task text **AND** the surface the request came from (CLI, Telegram, Slack, Web), session state, and a shared cross-surface episodic memory.

Built as an open-ended, modular monorepo scaffold designed for a team of 8 engineers working in parallel without stepping on each other.

---

## Quickstart & Demo

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

### 3. Run the Interactive CLI Demo
Launch the working CLI demo REPL:
```bash
uv run python -m orchestrator.cli_entry
# or:
make demo
```
In the demo:
- Typing any message flows through: `Gateway` -> `Identity` -> `Surface Policy` -> `Router (Mock)` -> `Persona` -> `Runtime (Echo)` -> `Memory Persistence (Stub)` -> `Formatted Reply`.
- Every reply includes the mandatory routing explanation line:
  ```
  [ROUTING] Summoned coder because Selected 'coder' on surface 'cli' (urgency: False). (autonomy: semi, confidence: 0.95)
  ```

You can also run one-shot queries directly:
```bash
uv run python -m orchestrator.cli_entry "Urgent: fix the production payment endpoint"
```

### 4. Run Tests, Linting & Evals
```bash
# Run full pytest suite (smoke tests + unit tests)
uv run pytest -v

# Run linting and type-checking
uv run ruff check .
uv run mypy .

# Run the routing evaluation benchmark harness
uv run python -m evals.runner
```

---

## Repository Map & Module Breakdown

```text
/packages
  /contracts            shared Pydantic schemas (the ONLY thing every module may import)
  /surfaces
    /telegram_slack     A1  chat adapter (stub)
    /cli                A2  CLI adapter (working minimal REPL against the mock pipeline)
  /gateway              A3  event normalizer: raw surface input -> RequestEnvelope
  /identity             A4  resolve_user(surface, external_id) (in-memory/config-file stub)
  /routing
    /surface_policy     B1  surface profiles + urgency rules (YAML-driven)
    /router             B2  Router interface + MockRouter returning a fixed RouteDecision
    /session            B3  session state manager (in-memory stub)
  /personas
    /registry           C1  loads persona YAML files; includes 4 placeholder personas (coder, researcher, ops, writer)
    /runtime            C2  agent runtime interface + EchoRuntime stub + MockLLMProvider
    /tools_core         C3  ToolSpec, tool registry, tool_scope enforcer (interface + stub)
    /tools_impl         C4  empty plugin folder with one example "echo" tool
  /safety
    /risk_classifier    D1  classify(ActionRequest) -> risk level (stub: everything "low")
    /approval           D2  approval request/response interface + auto-approve stub
  /memory
    /store              E1  schema + migrations + repository interface (+ in-memory repo)
    /writer             E2  write_memory(interaction) interface + stub
    /retriever          E3  retrieve(query, context) interface + stub
  /transparency
    /routing_log        F1  renders "Summoned <persona> because ..." + structured log
/apps
  /orchestrator         wires everything together from config; the end-to-end entry point
/evals                  F2  empty harness: labeled routing cases file + runner
/infra                  F3  docker-compose.yml (postgres+pgvector reference), .env.example
/config                 surfaces.yaml, personas/*.yaml, models.yaml (slots with provider "unset")
/docs                   architecture.md, contracts.md, adding-a-module.md, decisions/ (ADRs)
CODEOWNERS, Makefile, pyproject.toml (workspace), .pre-commit-config.yaml, README.md
```

---

## Core Architecture Principles

1. **Contracts First**: All shared types live in `packages/contracts/`. Modules depend **only** on `/contracts` and on interfaces (Python `Protocol`s), never on another module's concrete implementation.
2. **Pluggable Registries**: Adapters, tools, personas, router engines, runtimes, and memory backends register themselves into lightweight registries (`RouterRegistry`, `RuntimeRegistry`, `ToolRegistry`, `MemoryStoreRegistry`) and are selected via `config/*.yaml`.
3. **Vendor Agnostic**: Zero hardcoded vendor SDK dependencies. The LLM provider protocol (`complete()`, `structured()`) ships with a `MockLLMProvider`, leaving model slots configured as `unset` in `config/models.yaml`.
4. **Day-1 Execution Without Docker**: The default setup runs entirely in-memory using pure Python. Postgres + pgvector migrations and Docker Compose definitions are provided in `/infra` for future deployment.

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
