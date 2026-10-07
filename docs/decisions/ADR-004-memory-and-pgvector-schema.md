# ADR-004: Dual In-Memory and Postgres+pgvector Memory Backend

## Status
Accepted

## Context
Cross-surface memory requires vector similarity search for production scale, but developers and CI environments should run locally without requiring active database servers or Docker containers on day 1.

## Decision
Define `MemoryRepository` protocol. Implement `InMemoryMemoryRepository` as the default day-1 backend. Provide SQL migrations (`001_initial_schema.sql`) and a Docker Compose reference configuration for Postgres + pgvector for future deployment.

## Consequences
- Day-1 tests, demos, and CI run instantly in pure Python memory without external service dependencies.
- Clear path to production vector search when the team transitions.
