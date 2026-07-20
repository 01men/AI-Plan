import sqlite3
from contextlib import contextmanager
from pathlib import Path


DDL = """
CREATE TABLE IF NOT EXISTS bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_agent_id INTEGER NOT NULL UNIQUE,
    external_agent_id TEXT,
    external_agent_name TEXT,
    external_workspace_id TEXT,
    external_project_id TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_task_id INTEGER NOT NULL UNIQUE,
    local_agent_id INTEGER NOT NULL,
    external_issue_id TEXT,
    external_issue_key TEXT,
    external_status TEXT,
    state TEXT NOT NULL DEFAULT 'queued',
    last_deliverable_hash TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    local_task_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_state ON runs(state, updated_at);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status, created_at);
"""


def connect(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(path: Path) -> None:
    conn = connect(path)
    try:
        conn.executescript(DDL)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_session(path: Path):
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()

