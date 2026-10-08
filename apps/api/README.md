# API Service (`apps/api`)

Ingress FastAPI service exposing HTTP, Server-Sent Events (SSE), and webhook endpoints for the Surface-Aware Agent Orchestration pipeline.

## Endpoints

- `GET /healthz`: Health check returning service status and version (`0.2.0`).
- `POST /v1/message`: Ingress endpoint for standard messages with idempotency key deduplication.
- `POST /v1/stream`: SSE streaming endpoint for interactive surfaces.
- `POST /v1/webhooks/telegram`: Ingress webhook adapter for Telegram bot updates.
- `POST /v1/webhooks/slack`: Ingress webhook adapter for Slack event callbacks.
- `POST /v1/approvals/{request_id}`: Decision endpoint for human-in-the-loop approvals (`approve` or `deny`).

## Idempotency

Requests to `/v1/message` can supply an `Idempotency-Key` HTTP header. Duplicate requests within the TTL window receive the previously cached response immediately without re-triggering execution.
