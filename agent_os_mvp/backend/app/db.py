from __future__ import annotations

import sqlite3
from contextlib import contextmanager
import os
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
_DB_PATH_WARNING: dict[str, Any] | None = None


def get_db_path() -> Path:
    configured = os.getenv("AGENT_OS_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return BASE_DIR / "data" / "agent_os.db"


def get_db_path_warning() -> dict[str, Any] | None:
    return _DB_PATH_WARNING


def _fallback_db_path(original: Path, reason: str) -> Path:
    global _DB_PATH_WARNING
    fallback_root = Path(os.getenv("AGENT_OS_DB_FALLBACK_DIR", "/tmp/agent_os_mvp_data")).expanduser().resolve()
    fallback_root.mkdir(parents=True, exist_ok=True)
    fallback = fallback_root / original.name
    _DB_PATH_WARNING = {
        "code": "DASHBOARD_DATA_PATH_INVALID",
        "configured_db_path": str(original),
        "fallback_db_path": str(fallback),
        "reason": reason,
    }
    return fallback


def _ensure_db_parent(db_path: Path) -> Path:
    global _DB_PATH_WARNING
    parent = db_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        return _fallback_db_path(db_path, f"Configured database parent exists but is not a directory: {parent}")
    except OSError as exc:
        return _fallback_db_path(db_path, f"Could not create configured database parent {parent}: {exc}")
    if not parent.is_dir():
        return _fallback_db_path(db_path, f"Configured database parent is not a directory: {parent}")
    _DB_PATH_WARNING = None
    return db_path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    result_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL,
    task_id INTEGER,
    agent_role TEXT NOT NULL,
    tool_name TEXT,
    status TEXT NOT NULL,
    input_payload TEXT NOT NULL,
    output_payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    reviewer_role TEXT NOT NULL,
    verdict TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workbuddies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    primary_role TEXT NOT NULL,
    buddy_role TEXT NOT NULL,
    collaboration_note TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'suggested',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER,
    task_id INTEGER,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_company_runs (
    run_id TEXT PRIMARY KEY,
    spec_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    overall_status TEXT NOT NULL,
    started_at TEXT,
    goal TEXT NOT NULL,
    decision_summary TEXT NOT NULL,
    meeting_status TEXT NOT NULL,
    artifact_score REAL,
    active_agent_count INTEGER NOT NULL DEFAULT 0,
    alerts_json TEXT NOT NULL DEFAULT '[]',
    payload_json TEXT NOT NULL,
    synced_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    db_path = _ensure_db_parent(get_db_path())
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.executescript(SCHEMA_SQL)
        connection.commit()


@contextmanager
def get_db():
    connection = _connect()
    try:
        yield connection
    finally:
        connection.close()
