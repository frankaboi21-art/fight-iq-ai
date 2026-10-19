"""Small transactional store: PostgreSQL in production, SQLite for development/tests."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading

from fastapi import HTTPException
from app.core.config import get_settings

_initialized = set()
_lock = threading.Lock()
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS athletes (id TEXT PRIMARY KEY, handle TEXT UNIQUE NOT NULL, password TEXT NOT NULL, recovery TEXT NOT NULL, profile TEXT NOT NULL, created DOUBLE PRECISION NOT NULL)",
    "CREATE TABLE IF NOT EXISTS athlete_sessions (token TEXT PRIMARY KEY, athlete TEXT NOT NULL REFERENCES athletes(id) ON DELETE CASCADE, expires DOUBLE PRECISION NOT NULL)",
    "CREATE TABLE IF NOT EXISTS training_entries (id TEXT PRIMARY KEY, athlete TEXT NOT NULL REFERENCES athletes(id) ON DELETE CASCADE, data TEXT NOT NULL, created DOUBLE PRECISION NOT NULL)",
    "CREATE INDEX IF NOT EXISTS training_owner ON training_entries(athlete, created)",
    "CREATE TABLE IF NOT EXISTS coach_grants (owner TEXT NOT NULL REFERENCES athletes(id) ON DELETE CASCADE, coach TEXT NOT NULL REFERENCES athletes(id) ON DELETE CASCADE, PRIMARY KEY(owner, coach))",
    "CREATE TABLE IF NOT EXISTS coach_comments (id TEXT PRIMARY KEY, entry TEXT NOT NULL REFERENCES training_entries(id) ON DELETE CASCADE, author TEXT NOT NULL REFERENCES athletes(id) ON DELETE CASCADE, body TEXT NOT NULL, created DOUBLE PRECISION NOT NULL)",
    "CREATE TABLE IF NOT EXISTS attempts (kind TEXT, identity TEXT, created DOUBLE PRECISION)",
    "CREATE INDEX IF NOT EXISTS attempts_lookup ON attempts(kind, created)",
    "CREATE TABLE IF NOT EXISTS tactical_systems (id TEXT PRIMARY KEY, athlete TEXT NOT NULL REFERENCES athletes(id) ON DELETE CASCADE, data TEXT NOT NULL)",
)


def available():
    cfg = get_settings()
    return bool(cfg.database_url) or cfg.environment != "production"


class Connection:
    def __init__(self, raw, postgres):
        self.raw, self.postgres = raw, postgres

    def execute(self, query, values=()):
        return self.raw.execute(query.replace("?", "%s") if self.postgres else query, values)

    def lock_owner(self, owner):
        # SQLite transactions already hold a write lock. Serialize per athlete on Postgres.
        suffix = " FOR UPDATE" if self.postgres else ""
        return self.execute("SELECT id FROM athletes WHERE id=?" + suffix, (owner,)).fetchone()


@contextmanager
def transaction():
    cfg = get_settings()
    if not available():
        raise HTTPException(503, "Saved training is awaiting its persistent database setup.")
    postgres = bool(cfg.database_url)
    key = cfg.database_url if postgres else cfg.training_db_path
    raw = None
    try:
        if postgres:
            import psycopg
            raw = psycopg.connect(cfg.database_url, connect_timeout=8, options="-c statement_timeout=10000")
        else:
            Path(key).parent.mkdir(parents=True, exist_ok=True)
            raw = sqlite3.connect(key, timeout=8)
            raw.execute("PRAGMA foreign_keys=ON")
        db = Connection(raw, postgres)
        with _lock:
            if key not in _initialized:
                if postgres:
                    db.execute("SELECT pg_advisory_xact_lock(481092)")
                for statement in SCHEMA:
                    db.execute(statement)
                raw.commit()
                _initialized.add(key)
        if not postgres:
            raw.execute("BEGIN IMMEDIATE")
        yield db
        raw.commit()
    except HTTPException:
        if raw:
            raw.rollback()
        raise
    except Exception:
        if raw:
            raw.rollback()
        # Connection strings and submitted content must never reach the client.
        raise HTTPException(503, "Saved training is temporarily unavailable. Your changes were not saved.") from None
    finally:
        if raw:
            raw.close()
