import sqlite3
from contextlib import contextmanager
from pathlib import Path


DDL = """
CREATE TABLE IF NOT EXISTS resources (
 id TEXT PRIMARY KEY, type TEXT NOT NULL CHECK(type IN ('agent','knowledge_base','skill','mcp')),
 name TEXT NOT NULL, owner TEXT NOT NULL, endpoint TEXT, auth_profile_ref TEXT,
 execution_domain TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'registered',
 capability_manifest TEXT, data_scope_template TEXT NOT NULL DEFAULT '[]',
 tool_policy TEXT NOT NULL DEFAULT '[]', write_policy TEXT NOT NULL DEFAULT 'forbid',
 cost_policy TEXT NOT NULL DEFAULT '{}', health_profile TEXT NOT NULL DEFAULT '{}',
 version TEXT, trust_level TEXT NOT NULL DEFAULT 'sandbox', approval_required INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_verified_at TEXT, paused_reason TEXT
);
CREATE TABLE IF NOT EXISTS resource_bindings (
 id TEXT PRIMARY KEY, resource_id TEXT NOT NULL REFERENCES resources(id), scope_kind TEXT NOT NULL,
 scope_ref TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, approval_ticket_id TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(resource_id,scope_kind,scope_ref)
);
CREATE TABLE IF NOT EXISTS capability_manifests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, resource_id TEXT NOT NULL REFERENCES resources(id),
 version TEXT, source TEXT NOT NULL, payload TEXT NOT NULL, discovered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_contracts (
 id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, subject TEXT NOT NULL,
 initiator TEXT NOT NULL, resource_id TEXT NOT NULL REFERENCES resources(id),
 role TEXT NOT NULL, skills TEXT NOT NULL, tools TEXT NOT NULL, data_scope TEXT NOT NULL,
 write_policy TEXT NOT NULL, runtime TEXT NOT NULL, authorization TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'Draft', version INTEGER NOT NULL DEFAULT 1,
 input_payload TEXT NOT NULL DEFAULT '{}', result_summary TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dispatch_outbox (
 id TEXT PRIMARY KEY, contract_id TEXT NOT NULL REFERENCES task_contracts(id), kind TEXT NOT NULL,
 payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 available_at TEXT NOT NULL, lease_until TEXT, leased_by TEXT, external_run_id TEXT, error TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ext_agent_runs (
 id TEXT PRIMARY KEY, contract_id TEXT NOT NULL UNIQUE REFERENCES task_contracts(id), resource_id TEXT NOT NULL,
 external_run_id TEXT, external_task_id TEXT, state TEXT NOT NULL, last_sequence INTEGER NOT NULL DEFAULT 0,
 started_at TEXT, finished_at TEXT, last_reconciled_at TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES ext_agent_runs(id), event_id TEXT NOT NULL,
 sequence INTEGER NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(run_id,event_id), UNIQUE(run_id,sequence)
);
CREATE TABLE IF NOT EXISTS artifacts (
 id TEXT PRIMARY KEY, contract_id TEXT NOT NULL REFERENCES task_contracts(id), run_id TEXT,
 kind TEXT NOT NULL, content TEXT NOT NULL, provenance TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_review',
 reviewer TEXT, review_comment TEXT, created_at TEXT NOT NULL, reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS approval_tickets (
 id TEXT PRIMARY KEY, contract_id TEXT, level TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 requested_by TEXT NOT NULL, approved_by TEXT, reason TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, correlation_id TEXT, actor TEXT NOT NULL, action TEXT NOT NULL,
 target TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dead_letters (
 id INTEGER PRIMARY KEY AUTOINCREMENT, outbox_id TEXT NOT NULL, reason TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, replayed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_outbox_ready ON dispatch_outbox(status,available_at);
CREATE INDEX IF NOT EXISTS ix_events_run ON run_events(run_id,sequence);
"""


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db(path: Path):
    conn = connect(path)
    try:
        conn.executescript(DDL)
    finally:
        conn.close()


@contextmanager
def session(path: Path):
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()
