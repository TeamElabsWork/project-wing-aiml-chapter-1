# Contributing Guidelines

Welcome to **Surface-Aware Agent Orchestration**! This repository is designed as a modular monorepo so our team can build features, adapters, and tools simultaneously in parallel without merge conflicts.

---

## 1. Issue Management & Difficulty Tiers

Issues in this repository are assigned labels to help team members pick tasks matching their focus and availability:

### Difficulty Labels
| Label | Description | Examples |
| :--- | :--- | :--- |
| `difficulty:easy` | Great for onboarding, quick wins, docs, test coverage, and mock improvements. | Adding a new tool to `personas/tools_impl`, writing unit tests for policy rules, updating docs. |
| `difficulty:medium` | Implementing an adapter or subsystem behind an established protocol. | Building the Telegram bot adapter (`A1`), implementing the YAML surface policy engine (`B1`), adding Redis session caching. |
| `difficulty:hard` | Core architectural components, complex prompts, vector retrieval, or security. | Building the production LLM router (`B2`), pgvector similarity retrieval with HNSW indexing (`E1`), multi-step ReAct agent runtime (`C2`). |

### Module Labels
* `module:contracts` — Shared Pydantic data schemas.
* `module:surfaces` — CLI, Telegram, Slack adapters.
* `module:gateway` — Input normalization and identity mapping.
* `module:routing` — Surface policies, router engine, and session management.
* `module:personas` — Persona registry, agent runtimes, tool core, and tool plugins.
* `module:safety` — Risk classifier and human approval gates.
* `module:memory` — Repository store, memory extraction writer, and memory retriever.
* `module:evals` — Benchmark cases and routing evaluation harness.

> [!IMPORTANT]
> **Claiming an Issue**: Before starting work, comment on the issue and assign yourself (or ping the team) to avoid duplicate work.

---

## 2. Development Setup

We use **[uv](https://github.com/astral-sh/uv)** for high-speed package and virtual environment management.

### Prerequisites
* Python 3.11+
* `uv` installed (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
* Git

### Step-by-Step Setup
1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd project-wing-aiml-chapter-1
   ```
2. Install all workspace members and development dependencies:
   ```bash
   uv sync --all-packages --extra dev
   ```
3. Set up pre-commit hooks:
   ```bash
   uv run pre-commit install
   ```

---

## 3. Branching & Development Workflow

1. Create a branch from `main`:
   * Feature: `feat/<module>-<short-description>` (e.g., `feat/routing-llm-engine`)
   * Bug fix: `fix/<issue-id>-<short-description>` (e.g., `fix/12-telegram-markdown-parse`)
   * Docs/Evals: `docs/<description>` or `evals/<description>`
2. Work strictly inside your package directory (e.g. `packages/routing/router/`).
3. Follow the **Extensibility Rules**:
   * **Only import `contracts` directly**: Never import another module's concrete implementation.
   * **Use Registries**: Register your implementation via registries (`RouterRegistry`, `RuntimeRegistry`, `ToolRegistry`, `MemoryStoreRegistry`) and select it via config.
   * **Do not add heavy external services**: Core unit tests and smoke tests must run offline with working stubs.

---

## 4. Quality Checks Before Committing

Before opening a PR, ensure all three verification commands pass:

```bash
# 1. Format and lint checks
uv run ruff check .
uv run ruff format --check .

# 2. Strict type checks
uv run mypy .

# 3. Test suite
uv run pytest -v

# 4. Routing evaluations harness
uv run python -m evals.runner
```

To automatically format code:
```bash
uv run ruff check --fix .
uv run ruff format .
```

---

## 5. Submitting a Pull Request (PR)

### PR Title Convention
Follow Conventional Commits:
* `feat(router): implement few-shot router with fallback`
* `fix(gateway): resolve Telegram webhook payload parsing`
* `docs(contracts): document memory node embedding format`
* `test(policy): add urgency detection boundary tests`

### PR Description Checklist
Your PR description should include:
- [ ] Link to the issue it resolves (`Closes #<issue-number>`).
- [ ] Summary of changes made and files modified.
- [ ] Mention if any configuration (`config/*.yaml`) was added or altered.
- [ ] Confirmation that `ruff`, `mypy`, `pytest`, and `evals` pass locally.

> [!WARNING]
> ### The Contracts Stability Rule
> If your PR modifies files in `packages/contracts/`:
> 1. You **must** explain why the schema change is necessary.
> 2. The PR requires explicit review and sign-off from all affected module owners listed in `CODEOWNERS`.
> 3. Breaking field removals or renames are generally forbidden without a version migration.

---

## 6. Code Reviews & Ownership (`CODEOWNERS`)

### How CODEOWNERS Works
1. **Initial Setup (Manual 1-time step)**: Open [`CODEOWNERS`](file:///c:/Users/KIIT/Documents/GitHub/project-wing-aiml-chapter-1/CODEOWNERS) and replace your module's placeholder handle (e.g. `@owner-router`) with your real GitHub username (e.g. `@yourhandle`).
2. **Automatic Review Routing (GitHub Automated)**: Once your handle is saved in `CODEOWNERS`, you do **not** need to manually assign reviewers. GitHub automatically:
   * Requests your review whenever someone touches code inside your package folder.
   * Requests review from all dependent package owners whenever someone attempts to modify `packages/contracts/`.
3. **Merging**: A PR can be merged once GitHub Actions CI passes and the designated module owner(s) approve the changes.
