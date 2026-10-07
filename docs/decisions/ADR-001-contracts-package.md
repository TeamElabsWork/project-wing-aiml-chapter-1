# ADR-001: Central Contracts Package as the Sole Shared Dependency

## Status
Accepted

## Context
A team of 8 engineers is developing interconnected modules (Gateway, Routing, Memory, Personas, Safety, Surfaces) in parallel. Direct module-to-module dependencies create tight coupling, circular imports, and merge conflicts.

## Decision
All data schemas are isolated in `packages/contracts` as Pydantic v2 models. Every module may import `contracts`, but no module may import concrete implementations from another module. Communication across boundaries relies exclusively on Python Protocols and contracts.

## Consequences
- Prevents cross-module merge conflicts.
- Any change to `contracts` requires review from affected module owners (`CODEOWNERS`).
