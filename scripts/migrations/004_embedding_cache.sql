-- Migration 004: Embedding Cache
-- Created: 2026-02-02

-- Persistent embedding cache for performance optimization
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model_version TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0
);

-- Index for LRU eviction
CREATE INDEX IF NOT EXISTS idx_embedding_cache_lru ON embedding_cache(last_accessed);
CREATE INDEX IF NOT EXISTS idx_embedding_cache_model ON embedding_cache(model_version);
