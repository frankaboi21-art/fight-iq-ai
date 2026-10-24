"""Invite-only beta access and atomic, shared-on-disk request allowances.

Use one Render instance. The free service's ephemeral disk is not a billing cap;
redeploying can reset counters. Monitor OpenAI usage and project budget alerts as well.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException, Request

from app.core.config import get_settings

COOKIE_NAME = "fightiq_session"


def access_ready() -> bool:
    return len(get_settings().beta_access_code) >= 20


def signature(value: str) -> str:
    return hmac.new(get_settings().beta_access_code.encode(),
                    ("fightiq-session-v1:" + value).encode(), hashlib.sha256).hexdigest()


def make_session() -> str:
    value = f"{int(time.time())}.{secrets.token_hex(16)}"
    return f"{value}.{signature(value)}"


def session_id(request: Request) -> str | None:
    if not access_ready():
        return None
    token = request.cookies.get(COOKIE_NAME, "")
    if len(token) > 160:
        return None
    try:
        issued, nonce, supplied = token.split(".")
        age = time.time() - int(issued)
        if not (0 <= age <= get_settings().session_hours * 3600) or len(nonce) != 32:
            return None
        if not hmac.compare_digest(supplied, signature(f"{issued}.{nonce}")):
            return None
        return hashlib.sha256(nonce.encode()).hexdigest()
    except (ValueError, TypeError):
        return None


def require_session(request: Request) -> str:
    identity = session_id(request)
    if not identity:
        raise HTTPException(401, "Unlock AI Corner with your beta access code.")
    # Logged-in athletes keep the same AI allowance across beta unlocks/devices.
    if request.cookies.get("fightiq_athlete"):
        from app.core import database
        from app.services.training import account
        if database.available():
            with database.transaction() as db:
                try:
                    return account(request, db)["id"]
                except HTTPException as error:
                    if error.status_code != 401:
                        raise
    return identity


def require_same_origin(request: Request) -> None:
    # A custom header makes form-based CSRF impossible; CORS never permits
    # arbitrary origins. Check Origin too, including against the public host.
    if request.headers.get("x-fightiq-client") != "web":
        raise HTTPException(403, "Please send this request from Fight IQ AI.")
    origin = request.headers.get("origin")
    cfg = get_settings()
    expected_origin = cfg.public_origin or cfg.render_external_url or str(request.base_url)
    if origin and origin.rstrip("/") != expected_origin.rstrip("/"):
        raise HTTPException(403, "This request came from a different site.")


def _connection() -> sqlite3.Connection:
    path = Path(get_settings().usage_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS attempts (kind TEXT, identity TEXT, created REAL)")
        connection.execute("CREATE INDEX IF NOT EXISTS attempts_lookup ON attempts(kind, created)")
    except sqlite3.Error:
        connection.close()
        raise
    return connection


def consume_allowance(kind: str, identity: str) -> dict:
    """Reserve before calling the provider. Failures still count to bound spend.

    BEGIN IMMEDIATE serializes the check+insert across concurrent requests.
    Only hashes, event type and timestamps are stored, never submitted content.
    """
    now = time.time()
    cfg = get_settings()
    if kind == "login":
        limits = [(100, 900, None), (8, 900, identity)]
    elif kind == "video":
        limits = [(10, 86400, None), (3, 3600, None), (2, 900, identity)]
    elif kind == "round":
        limits = [(cfg.round_daily_limit, 86400, None), (cfg.round_hourly_limit, 3600, None), (36, 86400, identity)]
    else:
        limits = [(cfg.coach_daily_limit, 86400, None),
                  (cfg.coach_hourly_limit, 3600, None), (3, 900, identity)]
    if cfg.database_url:
        from app.core.database import transaction
        with transaction() as db:
            # Shared lock across instances makes reservations atomic and durable.
            db.execute("SELECT pg_advisory_xact_lock(481093)")
            db.execute("DELETE FROM attempts WHERE created < ?", (now - 86400,))
            for limit, seconds, owner in limits:
                query = "SELECT COUNT(*), MIN(created) FROM attempts WHERE kind=? AND created>?"
                args = [kind, now - seconds]
                if owner is not None:
                    query += " AND identity=?"
                    args.append(owner)
                count, oldest = db.execute(query, args).fetchone()
                if count >= limit:
                    raise HTTPException(429, "Request allowance reached. Please try again later.",
                                        headers={"Retry-After": str(max(1, int(oldest + seconds - now) + 1))})
            db.execute("INSERT INTO attempts VALUES (?,?,?)", (kind, identity, now))
        return {"session_limit": 3, "window_minutes": 15}
    connection = None
    try:
        connection = _connection()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM attempts WHERE created < ?", (now - 86400,))
        for limit, seconds, owner in limits:
            query = "SELECT COUNT(*), MIN(created) FROM attempts WHERE kind=? AND created>?"
            args: list = [kind, now - seconds]
            if owner is not None:
                query += " AND identity=?"
                args.append(owner)
            count, oldest = connection.execute(query, args).fetchone()
            if count >= limit:
                wait = max(1, int(oldest + seconds - now) + 1)
                raise HTTPException(429, "Request allowance reached. Please try again later.",
                                    headers={"Retry-After": str(wait)})
        connection.execute("INSERT INTO attempts VALUES (?, ?, ?)", (kind, identity, now))
        connection.commit()
        return {"session_limit": 3, "window_minutes": 15}
    except (sqlite3.Error, OSError):
        raise HTTPException(503, "Usage protection is temporarily unavailable. Please try again later.") from None
    finally:
        if connection is not None:
            connection.close()
