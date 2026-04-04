-- ============================================================
-- UMKA RAG System — Database Schema
-- Run this file once to set up the entire database
-- ============================================================

CREATE DATABASE IF NOT EXISTS rag_system
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE rag_system;

-- ── Table 1: sources ─────────────────────────────────────────
-- Stores one row per ingested source (PDF / URL / YouTube)
-- This is what the frontend's /sources endpoint returns
CREATE TABLE IF NOT EXISTS sources (
    id           VARCHAR(36)  PRIMARY KEY,           -- UUID e.g. "a1b2c3d4-..."
    type         ENUM('pdf','url','youtube') NOT NULL,
    title        VARCHAR(500) NOT NULL,               -- filename or page title or video title
    origin       TEXT         NOT NULL,               -- full file path OR full URL
    language     VARCHAR(10)  DEFAULT 'en',
    chunk_count  INT          DEFAULT 0,
    status       ENUM('processing','completed','failed') DEFAULT 'processing',
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- ── Table 2: chunks ──────────────────────────────────────────
-- Stores every text chunk extracted from every source
-- FAISS stores the vector, MySQL stores the actual text + metadata
CREATE TABLE IF NOT EXISTS chunks (
    id           VARCHAR(36)  PRIMARY KEY,           -- UUID, same ID used in FAISS
    source_id    VARCHAR(36)  NOT NULL,
    chunk_text   LONGTEXT     NOT NULL,
    chunk_index  INT          NOT NULL,              -- 0-based position in the source
    page_number  INT          DEFAULT NULL,          -- PDFs only
    timestamp_s  INT          DEFAULT NULL,          -- YouTube only (seconds)
    url_ref      TEXT         DEFAULT NULL,          -- URL sources only
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

-- ── Table 3: chat_history ────────────────────────────────────
-- Stores every question + answer permanently (fixes localStorage-only bug)
CREATE TABLE IF NOT EXISTS chat_history (
    id           VARCHAR(36)  PRIMARY KEY,
    question     TEXT         NOT NULL,
    answer       LONGTEXT     NOT NULL,
    sources_used JSON         DEFAULT NULL,          -- array of source IDs used
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- ── Indexes for faster queries ───────────────────────────────
CREATE INDEX idx_chunks_source_id  ON chunks(source_id);
CREATE INDEX idx_sources_type      ON sources(type);
CREATE INDEX idx_sources_created   ON sources(created_at);
CREATE INDEX idx_chat_created      ON chat_history(created_at);

use rag_system;
show tables;

SELECT id, type, title, chunk_count, status, created_at FROM sources;
SELECT chunk_index, page_number, LEFT(chunk_text, 80) FROM chunks WHERE source_id = '73c648d0-9b28-47af-a544-193fd069e891' LIMIT 5;

SELECT id, type, title, chunk_count, status, created_at FROM sources;

SELECT id, type, title, chunk_count, language, status, created_at 
FROM sources;

SELECT 
    chunk_index, 
    page_number, 
    timestamp_s, 
    url_ref,
    LEFT(chunk_text, 100) as preview
FROM chunks 
ORDER BY created_at DESC 
LIMIT 10;

USE rag_system;
SELECT 
    chunk_index,
    timestamp_s,
    CONCAT(timestamp_s DIV 60, 'm ', timestamp_s MOD 60, 's') as time_label,
    LEFT(chunk_text, 60) as preview
FROM chunks
WHERE source_id = '1e9708b6-2f3f-43ae-9a57-f6ab1f873313'
ORDER BY chunk_index;

USE rag_system;
DELETE FROM sources WHERE id = '78b0ced2-d91a-4570-af47-f36d4ac84d9f';