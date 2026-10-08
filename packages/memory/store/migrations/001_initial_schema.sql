-- Initial schema for cross-surface memory storage with pgvector
-- Owner: E1

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_nodes (
    node_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    surface VARCHAR(32) NOT NULL,
    project_tag VARCHAR(128),
    persona VARCHAR(64) NOT NULL,
    summary TEXT NOT NULL,
    embedding vector(1536),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Indices for rapid cross-surface lookups
CREATE INDEX IF NOT EXISTS idx_memory_nodes_user_id ON memory_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_surface ON memory_nodes(surface);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_project_tag ON memory_nodes(project_tag);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_timestamp ON memory_nodes(timestamp DESC);

-- Vector similarity search index (cosine distance)
CREATE INDEX IF NOT EXISTS idx_memory_nodes_embedding ON memory_nodes USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
