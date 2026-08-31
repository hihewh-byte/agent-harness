-- Tax Agent persistence schema (v1 draft)
-- SQLite-compatible; adapt types for PostgreSQL in production

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tax_payer_profile (
    profile_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    resident_status TEXT NOT NULL CHECK (resident_status IN ('cn_tax_resident', 'non_resident', 'uncertain')),
    tax_residency_country TEXT NOT NULL DEFAULT 'CN',
    id_document_hash TEXT,
    declared_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tax_session (
    session_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES tax_payer_profile(profile_id),
    tax_year INTEGER NOT NULL,
    fx_policy TEXT NOT NULL,
    filing_scope TEXT NOT NULL CHECK (filing_scope IN ('foreign_only', 'includes_domestic')),
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS uploaded_document (
    document_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES tax_session(session_id),
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    broker_template_id TEXT,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS account_source (
    account_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES tax_session(session_id),
    broker_template_id TEXT NOT NULL,
    broker_name TEXT NOT NULL,
    country TEXT NOT NULL,
    account_currency TEXT NOT NULL DEFAULT 'USD',
    account_number_masked TEXT
);

CREATE TABLE IF NOT EXISTS tax_event (
    event_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES account_source(account_id),
    event_type TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    settle_date TEXT,
    symbol TEXT,
    quantity TEXT,
    gross_amount TEXT NOT NULL,
    gross_currency TEXT NOT NULL,
    withholding_amount TEXT,
    withholding_currency TEXT,
    fee_amount TEXT,
    fee_currency TEXT,
    amount_cny TEXT,
    fx_rate_used REAL,
    fx_rate_date TEXT,
    description TEXT,
    source_row_ref TEXT NOT NULL,
    parse_confidence REAL NOT NULL,
    classification_status TEXT NOT NULL,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_tax_event_account_date ON tax_event(account_id, trade_date);

CREATE TABLE IF NOT EXISTS fx_rate_record (
    fx_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES tax_session(session_id),
    rate_date TEXT NOT NULL,
    from_currency TEXT NOT NULL,
    to_currency TEXT NOT NULL DEFAULT 'CNY',
    rate REAL NOT NULL,
    source TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rule_snapshot (
    rule_snapshot_id TEXT PRIMARY KEY,
    rule_pack_id TEXT NOT NULL,
    version_label TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    checksum TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'review', 'stable', 'deprecated')),
    payload_json TEXT NOT NULL,
    published_at TEXT
);

CREATE TABLE IF NOT EXISTS computation_run (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES tax_session(session_id),
    rule_snapshot_id TEXT NOT NULL REFERENCES rule_snapshot(rule_snapshot_id),
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    summary_json TEXT,
    audit_bundle_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tax_line_item (
    line_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES computation_run(run_id),
    tax_category TEXT NOT NULL,
    taxable_income_cny TEXT NOT NULL,
    tax_rate REAL NOT NULL,
    tax_due_cny TEXT NOT NULL,
    foreign_tax_paid_cny TEXT,
    credit_allowed_cny TEXT,
    net_tax_due_cny TEXT NOT NULL,
    source_event_ids_json TEXT NOT NULL,
    formula_steps_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES computation_run(run_id),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    detail_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
