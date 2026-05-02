-- backend/database/schema.sql — CLEAN VERSION (remove all SELECT/DELETE debug lines)

CREATE DATABASE IF NOT EXISTS rag_system
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE rag_system;

CREATE TABLE IF NOT EXISTS sources (
    id           VARCHAR(36)  PRIMARY KEY,
    type         ENUM('pdf','url','youtube') NOT NULL,
    title        VARCHAR(500) NOT NULL,
    origin       TEXT         NOT NULL,
    language     VARCHAR(10)  DEFAULT 'en',
    chunk_count  INT          DEFAULT 0,
    status       ENUM('processing','completed','failed') DEFAULT 'processing',
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id           VARCHAR(36)  PRIMARY KEY,
    source_id    VARCHAR(36)  NOT NULL,
    chunk_text   LONGTEXT     NOT NULL,
    chunk_index  INT          NOT NULL,
    page_number  INT          DEFAULT NULL,
    timestamp_s  INT          DEFAULT NULL,
    url_ref      TEXT         DEFAULT NULL,
    chunk_type   ENUM('text','legal','image') DEFAULT 'text',
    legal_metadata JSON       DEFAULT NULL,
    image_path   VARCHAR(500) DEFAULT NULL,
    unified_metadata JSON     DEFAULT NULL,
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conversations (
    id           VARCHAR(36)  PRIMARY KEY,
    title        VARCHAR(500) DEFAULT 'New Chat',
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    id              VARCHAR(36)  PRIMARY KEY,
    conversation_id VARCHAR(36)  DEFAULT NULL,
    question        TEXT         NOT NULL,
    answer          LONGTEXT     NOT NULL,
    sources_used    JSON         DEFAULT NULL,
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_sources (
    id            VARCHAR(36) PRIMARY KEY,
    source_id     VARCHAR(36) NOT NULL,
    doc_type      ENUM('statute','judgment','constitution') NOT NULL,
    court         VARCHAR(200) DEFAULT NULL,
    judgment_date DATE         DEFAULT NULL,
    ipc_sections  JSON         DEFAULT NULL,
    petitioner    VARCHAR(500) DEFAULT NULL,
    respondent    VARCHAR(500) DEFAULT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS image_jobs (
    id            VARCHAR(36) PRIMARY KEY,
    source_id     VARCHAR(36) NOT NULL,
    image_path    VARCHAR(500) NOT NULL,
    status        ENUM('pending','processing','completed','failed') DEFAULT 'pending',
    caption       TEXT         DEFAULT NULL,
    error_message TEXT         DEFAULT NULL,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_type      ON chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_sources_type     ON sources(type);
CREATE INDEX IF NOT EXISTS idx_sources_created  ON sources(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_created     ON chat_history(created_at);