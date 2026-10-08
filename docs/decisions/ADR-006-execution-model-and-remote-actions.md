# ADR-006: Code Execution Model and Remote Actions

## Status
Accepted

## Context
When an agent is requested to modify code, refactor a project, or execute developer tasks, how should the changes be executed safely across different surfaces (CLI, Telegram, Slack, Web)?

Key considerations:
1. Allowing the agent to edit files or run arbitrary bash commands directly on the central backend server poses critical security risks and filesystem pollution.
2. Running an SSH server on the backend to allow remote terminal access introduces attack surface, SSH key management overhead, and high maintenance.
3. Heavy ephemeral cloud sandboxes (e.g. E2B, Modal, microVMs) add operational complexity, billing friction, and cold-start latency for day-1/v1 deployments.

## Decision
1. **Remote Surfaces (Telegram, Slack, Web)**: The agent executes code changes via **GitHub App / Git API operations**. It clones/fetches the repository, creates an isolated feature branch, commits proposed modifications, and opens a Pull Request. This makes all changes reviewable, auditable, and decoupled from server disk.
2. **Local Surface (CLI)**: When running via the CLI adapter on a developer's workstation, tool execution (reading files, applying patches) runs client-side in the developer's local environment where the workspace already exists.
3. **No SSH Server**: We explicitly reject running an SSH server daemon on the orchestrator backend. CLI interactions connect over standard HTTPS / WebSockets / SSE.
4. **No Heavy Server Sandboxes**: Cloud sandboxes are deferred until multi-tenant remote shell execution is strictly required.

## Consequences
- Zero security risk of remote users running destructive scripts on the central host.
- Fully auditable git workflows via Pull Requests for non-CLI requests.
- Lightweight, portable CLI client for local developers.
