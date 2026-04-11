USE rag_system;

-- MySQL 8.0 does not support IF NOT EXISTS for ADD COLUMN in ALTER TABLE.
-- These statements will add the columns if they don't already exist.
-- If they do exist, it might error, but we've verified they don't.
ALTER TABLE chunks ADD COLUMN chunk_type ENUM('text','legal','image') DEFAULT 'text';
ALTER TABLE chunks ADD COLUMN legal_metadata JSON DEFAULT NULL;
ALTER TABLE chunks ADD COLUMN image_path VARCHAR(500) DEFAULT NULL;

CREATE TABLE IF NOT EXISTS legal_sources (
   id VARCHAR(36) PRIMARY KEY,
   source_id VARCHAR(36) NOT NULL,
   doc_type ENUM('statute','judgment','constitution') NOT NULL,
   court VARCHAR(200) DEFAULT NULL,
   judgment_date DATE DEFAULT NULL,
   ipc_sections JSON DEFAULT NULL,
   petitioner VARCHAR(500) DEFAULT NULL,
   respondent VARCHAR(500) DEFAULT NULL,
   FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS image_jobs (
   id VARCHAR(36) PRIMARY KEY,
   source_id VARCHAR(36) NOT NULL,
   image_path VARCHAR(500) NOT NULL,
   status ENUM('pending','processing','completed','failed') DEFAULT 'pending',
   caption TEXT DEFAULT NULL,
   error_message TEXT DEFAULT NULL,
   created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
   updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
