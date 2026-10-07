-- Initial database schema for Cross-Surface Agent Memory
-- Enables pgvector extension for dense vector similarity search

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Table: memory_nodes
CREATE TABLE IF NOT EXISTS memory_nodes (
    node_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    surface VARCHAR(32) NOT NULL,
    project_tag VARCHAR(64),
    persona VARCHAR(32) NOT NULL,
    summary TEXT NOT NULL,
    embedding vector(1536), -- Standard embedding dimension placeholder (can be altered per model)
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Indices for efficient filtering
CREATE INDEX IF NOT EXISTS idx_memory_user_id ON memory_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_surface ON memory_nodes(surface);
CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory_nodes(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_memory_metadata ON memory_nodes USING gin(metadata);

-- HNSW Vector Index for fast cosine similarity search
-- (Uncomment when pgvector is active)
-- CREATE INDEX IF NOT EXISTS idx_memory_embedding_hnsw
-- ON memory_nodes USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);
