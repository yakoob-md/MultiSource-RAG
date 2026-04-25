USE rag_system;

-- Add column (Standard MySQL syntax - IF NOT EXISTS not supported for ADD COLUMN)
ALTER TABLE chunks ADD COLUMN unified_metadata JSON DEFAULT NULL;

-- Functional indexes (Requires CAST in MySQL 8.0 for JSON strings to avoid BLOB/TEXT error)
CREATE INDEX idx_chunks_source_type ON chunks((CAST(unified_metadata->>'$.source_type' AS CHAR(32))));
CREATE INDEX idx_chunks_domain ON chunks((CAST(unified_metadata->>'$.domain' AS CHAR(32))));
CREATE INDEX idx_chunks_section ON chunks((CAST(unified_metadata->>'$.section_id' AS CHAR(64))));
