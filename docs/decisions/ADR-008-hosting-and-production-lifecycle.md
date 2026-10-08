# ADR-008: Production Hosting Strategy and Lifecycle Management

## Status
Accepted

## Context
Deploying an autonomous agent orchestrator presents unique operational challenges:
- LLM reasoning chains and tool calls often exceed 10–30 seconds.
- Incoming surfaces (Telegram, Slack webhooks, WebSocket CLI) require different concurrency and connection models.
- The server process may crash due to unhandled exceptions, memory pressure, or node reboots.
- Hosting budgets require evaluating free/low-cost options (Vercel, Render, Oracle Cloud Free Tier).

## Decision
1. **Target Hosting Infrastructure**:
   - **Vercel Free Tier**: Rejected for orchestrator core due to strict 10–15 second serverless function timeouts and lack of persistent background threads.
   - **Render Free Tier**: Sub-optimal for production due to sleeping after 15 minutes of inactivity (50s cold-start penalty) and a 512MB RAM cap.
   - **Oracle Cloud Always Free VM (or $5/mo VPS)**: Recommended as the primary production host. Provides 4 OCPUs, 24GB RAM, 200GB persistent SSD, and continuous 24/7 uptime without sleep intervals.
2. **Crash Recovery & Process Supervision**:
   - Orchestrator processes run under `systemd` (`Restart=always`, `RestartSec=2s`) or Docker with `restart: unless-stopped`.
   - In the event of a fatal exception or process termination, the daemon is restarted in under 2 seconds.
3. **Session vs Long-Term Memory Lifecycle**:
   - **Sessions (Short-Term Working Context)**: Ephemeral conversations carry an inactivity TTL (e.g. 30–60 minutes). Stored in Redis or Postgres session tables.
   - **Memories (Long-Term Episodic Context)**: Persisted indefinitely in the Postgres database and indexed for cross-surface semantic retrieval.
4. **Message Idempotency**:
   - The `RequestEnvelope.message_id` serves as an idempotency key to prevent double-execution when webhook clients (e.g. Telegram) retry timed-out requests.

## Consequences
- Reliable, continuous background execution for multi-step agent reasoning.
- Fast, automated crash recovery with zero loss of persisted data.
- Stable Telegram bot long-polling or webhook processing without serverless timeout failures.
