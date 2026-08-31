-- Simplified runtime schema (v1) — dataset-centric, no mandatory payer profile

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tax_dataset (
    dataset_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    broker_template_id TEXT NOT NULL,
    data_quality_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tax_dataset_session ON tax_dataset(session_id);

CREATE TABLE IF NOT EXISTS tax_document (
    document_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES tax_dataset(dataset_id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tax_event_row (
    event_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES tax_dataset(dataset_id) ON DELETE CASCADE,
    event_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tax_event_dataset ON tax_event_row(dataset_id);

CREATE TABLE IF NOT EXISTS tax_report (
    run_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES tax_dataset(dataset_id) ON DELETE CASCADE,
    markdown TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_message (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    meta_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_message(session_id, created_at);

CREATE TABLE IF NOT EXISTS review_ticket (
    ticket_id TEXT PRIMARY KEY,
    run_id TEXT,
    dataset_id TEXT,
    session_id TEXT,
    risk_level TEXT NOT NULL DEFAULT 'high',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_review_ticket_status ON review_ticket(status, created_at);
