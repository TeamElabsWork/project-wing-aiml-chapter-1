# ADR-007: PostgreSQL + pgvector for Cross-Surface Memory Storage

## Status
Accepted

## Context
Agent orchestration requires cross-surface memory containing both:
- **Structured relational metadata**: `user_id`, `tenant_id`, origin `surface`, `timestamp`, `session_id`, `project_tag`.
- **Unstructured semantic data**: interaction summary text and high-dimensional vector embeddings (e.g. 1536 float dimensions).

We evaluated dedicated vector databases (Pinecone, Qdrant, Weaviate), local SQLite (`sqlite-vss`), MongoDB Atlas Vector Search, and PostgreSQL + `pgvector`.

## Decision
We select **PostgreSQL with the `pgvector` extension** as the primary storage layer for cross-surface memory:

1. **Avoids the "Two-Database Problem"**: Using a separate vector DB (like Pinecone) requires maintaining a relational DB for users/sessions alongside the vector store, creating dual-write consistency issues and split transaction boundaries.
2. **Hybrid Queries in Single SQL Statement**: Relational filters (`WHERE user_id = :uid AND surface = 'cli' AND timestamp > NOW() - INTERVAL '30 days'`) combine natively with cosine similarity search (`ORDER BY embedding <=> :vector LIMIT 5`).
3. **Generous Free-Tier Capacities**:
   - Each memory node consumes $\approx 9 \text{ KB}$ (summary, metadata, 1536-dim vector, HNSW index).
   - 500 MB free tiers (Supabase / Neon) accommodate $\approx 55,000$ discrete memories.
   - Self-hosted Postgres on a free VM (Oracle Free Tier 200GB SSD) accommodates millions of memories with zero external cost.
4. **Abstraction Independence**: All modules interact through the Python `MemoryRepository` protocol. The core pipeline never binds directly to raw Postgres/pgvector, allowing other backends to be plugged in if needed.

## Consequences
- Single unified database to backup, migrate, and secure.
- Zero extra external SaaS subscription costs.
- Full ACID transaction guarantees for memory writes.
