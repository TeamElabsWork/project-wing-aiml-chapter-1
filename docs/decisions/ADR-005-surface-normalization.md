# ADR-005: Gateway Normalization and Surface Context Decoupling

## Status
Accepted

## Context
Surface inputs originate from diverse platforms with conflicting payload structures (CLI args, Telegram JSON webhooks, Slack Block Kit events). Downstream modules (Router, Safety, Personas) should not need to understand platform-specific schemas.

## Decision
Surface adapters (`packages/surfaces/`) parse platform payloads and pass raw content to `gateway`, which packages them into an immutable `RequestEnvelope` embedding a `SurfaceContext` struct. Routing and reasoning operate only on the normalized envelope.

## Consequences
- Adding new chat apps or surfaces requires only creating a lightweight adapter that feeds into the Gateway.
- Core business logic remains strictly platform-agnostic.
