# ADR-011: Unified Memory Schema and Dynamic Vector Dimension Migration

## Status
Accepted

## Context
1. **Schema Duplication & Naming Discrepancy**:
   Previous scaffolding contained two migration files with diverging column names (`created_at` vs `timestamp`). Meanwhile, the core typed contract `MemoryNode` in `packages/contracts` uses `timestamp: datetime`.
2. **Hardcoded Vector Dimensions**:
   The pgvector table definition previously hardcoded `vector(1536)` directly in SQL, while `config/models.yaml` defines `embedding.dimensions: 1536` which may change depending on embedding model choice (e.g., 768 for small models, 3072 for larger models).

## Decision
1. **Standardize on `timestamp`**:
   Standardize the SQL column in `001_initial_schema.sql` to `timestamp` to match the `MemoryNode` Pydantic model contract.
2. **Single Canonical Migration**:
   Maintain exactly one canonical migration file at `packages/memory/store/migrations/001_initial_schema.sql` and remove the redundant duplicate inside `packages/memory/store/memory_store/migrations`. `infra/docker-compose.yml` mounts this canonical file.
3. **Dynamic Dimension Substitution Runner**:
   Implement a lightweight migration runner `scripts/migrate.py` invoked via `make migrate`. It reads `config/models.yaml`, extracts `embedding.dimensions`, and ensures the pgvector column definition in `001_initial_schema.sql` matches the configured dimension.

## Consequences
- Single source of truth for database migrations.
- Zero impedance mismatch between database columns and typed contracts.
- Frictionless configuration changes when switching embedding providers or dimension sizes.
