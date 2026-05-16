"""
Agent persistence — uses the same MySQL/PostgreSQL database as the Survey API.

Tables (created on init_db):
  agent_messages      — conversation history for LLM context
  agent_context       — per-user key/value (active service, pending CRUD fields)
  agent_sessions      — session metadata + interrupt state
  agent_user_profile  — default company, industry, preferences
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

try:
    import pymysql
except ImportError:
    pymysql = None  # type: ignore

try:
    import psycopg
except ImportError:
    psycopg = None  # type: ignore


@dataclass(frozen=True)
class DBConfig:
    engine: str
    host: str
    port: int
    database: str
    username: str
    password: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_config() -> DBConfig:
    dialect = (os.getenv("DB_DIALECT") or "mysql").lower()
    engine = "postgresql" if dialect in ("postgres", "postgresql", "pg") else "mysql"
    return DBConfig(
        engine=engine,
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306" if engine == "mysql" else "5432")),
        database=os.getenv("DB_DATABASE", "survey"),
        username=os.getenv("DB_USERNAME", "root"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def _connect(cfg: DBConfig):
    if cfg.engine == "postgresql":
        if psycopg is None:
            raise RuntimeError("Install psycopg: pip install psycopg[binary]")
        return psycopg.connect(
            host=cfg.host,
            port=cfg.port,
            dbname=cfg.database,
            user=cfg.username,
            password=cfg.password,
        )
    if pymysql is None:
        raise RuntimeError("Install pymysql: pip install pymysql")
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        database=cfg.database,
        user=cfg.username,
        password=cfg.password,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def _execute(conn, sql: str, params: tuple | dict = ()):
    cfg = get_db_config()
    if cfg.engine == "postgresql":
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def init_db() -> None:
    cfg = get_db_config()
    with _connect(cfg) as conn:
        if cfg.engine == "mysql":
            stmts = [
                """
                CREATE TABLE IF NOT EXISTS agent_messages (
                  id BIGINT AUTO_INCREMENT PRIMARY KEY,
                  user_id VARCHAR(64) NOT NULL,
                  session_id VARCHAR(64) NOT NULL DEFAULT 'default',
                  role VARCHAR(16) NOT NULL,
                  content TEXT NOT NULL,
                  intent VARCHAR(64) NULL,
                  service VARCHAR(64) NULL,
                  redo_count INT NOT NULL DEFAULT 0,
                  created_at DATETIME(6) NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_agent_msg_user ON agent_messages (user_id, session_id, id)",
                """
                CREATE TABLE IF NOT EXISTS agent_context (
                  user_id VARCHAR(64) NOT NULL,
                  ctx_key VARCHAR(128) NOT NULL,
                  ctx_value TEXT NOT NULL,
                  updated_at DATETIME(6) NOT NULL,
                  PRIMARY KEY (user_id, ctx_key)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS agent_sessions (
                  user_id VARCHAR(64) NOT NULL,
                  session_id VARCHAR(64) NOT NULL,
                  status VARCHAR(32) NOT NULL DEFAULT 'active',
                  pending_question TEXT NULL,
                  thread_id VARCHAR(128) NOT NULL,
                  updated_at DATETIME(6) NOT NULL,
                  PRIMARY KEY (user_id, session_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS agent_user_profile (
                  user_id VARCHAR(64) PRIMARY KEY,
                  default_company VARCHAR(255) NULL,
                  industry VARCHAR(255) NULL,
                  preferences JSON NULL,
                  updated_at DATETIME(6) NOT NULL
                )
                """,
            ]
            for sql in stmts:
                _execute(conn, sql)
            conn.commit()
            return

        stmts = [
            """
            CREATE TABLE IF NOT EXISTS agent_messages (
              id BIGSERIAL PRIMARY KEY,
              user_id TEXT NOT NULL,
              session_id TEXT NOT NULL DEFAULT 'default',
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              intent TEXT,
              service TEXT,
              redo_count INT NOT NULL DEFAULT 0,
              created_at TIMESTAMPTZ NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_agent_msg_user ON agent_messages (user_id, session_id, id)",
            """
            CREATE TABLE IF NOT EXISTS agent_context (
              user_id TEXT NOT NULL,
              ctx_key TEXT NOT NULL,
              ctx_value TEXT NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL,
              PRIMARY KEY (user_id, ctx_key)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agent_sessions (
              user_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              pending_question TEXT,
              thread_id TEXT NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL,
              PRIMARY KEY (user_id, session_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agent_user_profile (
              user_id TEXT PRIMARY KEY,
              default_company TEXT,
              industry TEXT,
              preferences JSONB,
              updated_at TIMESTAMPTZ NOT NULL
            )
            """,
        ]
        for sql in stmts:
            _execute(conn, sql)
        conn.commit()


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(
    user_id: str,
    role: str,
    content: str,
    *,
    intent: str | None = None,
    service: str | None = None,
    session_id: str | None = None,
    redo_count: int = 0,
) -> None:
    cfg = get_db_config()
    sid = session_id or "default"
    with _connect(cfg) as conn:
        _execute(
            conn,
            """
            INSERT INTO agent_messages
              (user_id, session_id, role, content, intent, service, redo_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, sid, role, content, intent, service, redo_count, _utc_now()),
        )
        conn.commit()


def get_history(user_id: str, limit: int = 50, session_id: str | None = None) -> list[dict[str, str]]:
    cfg = get_db_config()
    sid = session_id or "default"
    limit = max(1, min(limit, 200))
    with _connect(cfg) as conn:
        cur = _execute(
            conn,
            """
            SELECT role, content, intent, service, created_at
            FROM agent_messages
            WHERE user_id = ? AND session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, sid, limit),
        )
        if cfg.engine == "postgresql":
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in rows]
        else:
            rows = cur.fetchall()
    rows.reverse()
    return [
        {
            "role": r["role"] if isinstance(r, dict) else r[0],
            "content": r["content"] if isinstance(r, dict) else r[1],
            "intent": (r.get("intent") if isinstance(r, dict) else r[2]) or "",
            "service": (r.get("service") if isinstance(r, dict) else r[3]) or "",
            "created_at": str(r.get("created_at") if isinstance(r, dict) else r[4]),
        }
        for r in rows
    ]


def get_llm_context(user_id: str, limit: int = 8, session_id: str | None = None) -> list[dict[str, str]]:
    hist = get_history(user_id, limit=limit, session_id=session_id)
    return [{"role": h["role"], "content": h["content"]} for h in hist]


# ── Context (KV) ──────────────────────────────────────────────────────────────

def get_context(user_id: str) -> dict[str, Any]:
    cfg = get_db_config()
    with _connect(cfg) as conn:
        cur = _execute(conn, "SELECT ctx_key, ctx_value FROM agent_context WHERE user_id = ?", (user_id,))
        if cfg.engine == "postgresql":
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in rows]
        else:
            rows = cur.fetchall()
    out: dict[str, Any] = {}
    for row in rows:
        key = row["ctx_key"] if isinstance(row, dict) else row[0]
        raw = row["ctx_value"] if isinstance(row, dict) else row[1]
        try:
            out[key] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            out[key] = raw
    return out


def set_context(user_id: str, **kwargs: Any) -> None:
    cfg = get_db_config()
    now = _utc_now()
    with _connect(cfg) as conn:
        for key, value in kwargs.items():
            if value is None:
                _execute(conn, "DELETE FROM agent_context WHERE user_id = ? AND ctx_key = ?", (user_id, key))
            else:
                encoded = json.dumps(value) if not isinstance(value, str) else value
                if cfg.engine == "mysql":
                    _execute(
                        conn,
                        """
                        INSERT INTO agent_context (user_id, ctx_key, ctx_value, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON DUPLICATE KEY UPDATE ctx_value = VALUES(ctx_value), updated_at = VALUES(updated_at)
                        """,
                        (user_id, key, encoded, now),
                    )
                else:
                    _execute(
                        conn,
                        """
                        INSERT INTO agent_context (user_id, ctx_key, ctx_value, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (user_id, ctx_key) DO UPDATE SET
                          ctx_value = EXCLUDED.ctx_value,
                          updated_at = EXCLUDED.updated_at
                        """,
                        (user_id, key, encoded, now),
                    )
        conn.commit()


def get_pending_operation(user_id: str) -> dict[str, Any] | None:
    return get_context(user_id).get("pending_operation")


def set_pending_operation(user_id: str, op: dict[str, Any] | None) -> None:
    set_context(user_id, pending_operation=op)


# ── Sessions ──────────────────────────────────────────────────────────────────

def upsert_session(
    user_id: str,
    session_id: str,
    *,
    status: str = "active",
    pending_question: str | None = None,
) -> str:
    cfg = get_db_config()
    thread_id = f"{user_id}:{session_id}"
    now = _utc_now()
    with _connect(cfg) as conn:
        if cfg.engine == "mysql":
            _execute(
                conn,
                """
                INSERT INTO agent_sessions (user_id, session_id, status, pending_question, thread_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                  status = VALUES(status),
                  pending_question = VALUES(pending_question),
                  updated_at = VALUES(updated_at)
                """,
                (user_id, session_id, status, pending_question, thread_id, now),
            )
        else:
            _execute(
                conn,
                """
                INSERT INTO agent_sessions (user_id, session_id, status, pending_question, thread_id, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, session_id) DO UPDATE SET
                  status = EXCLUDED.status,
                  pending_question = EXCLUDED.pending_question,
                  updated_at = EXCLUDED.updated_at
                """,
                (user_id, session_id, status, pending_question, thread_id, now),
            )
        conn.commit()
    return thread_id


# ── User profile ──────────────────────────────────────────────────────────────

def get_profile(user_id: str) -> dict[str, Any]:
    cfg = get_db_config()
    with _connect(cfg) as conn:
        cur = _execute(
            conn,
            "SELECT default_company, industry, preferences FROM agent_user_profile WHERE user_id = ?",
            (user_id,),
        )
        if cfg.engine == "postgresql":
            row = cur.fetchone()
            if not row:
                return {}
            cols = [d[0] for d in cur.description]
            row = dict(zip(cols, row))
        else:
            row = cur.fetchone()
    if not row:
        return {}
    prefs = row.get("preferences") if isinstance(row, dict) else row[2]
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}
    return {
        "default_company": row.get("default_company") if isinstance(row, dict) else row[0],
        "industry": row.get("industry") if isinstance(row, dict) else row[1],
        "preferences": prefs or {},
    }


def upsert_profile(
    user_id: str,
    *,
    default_company: str | None = None,
    industry: str | None = None,
    preferences: dict | None = None,
) -> None:
    cfg = get_db_config()
    existing = get_profile(user_id)
    company = default_company if default_company is not None else existing.get("default_company")
    ind = industry if industry is not None else existing.get("industry")
    prefs = preferences if preferences is not None else existing.get("preferences", {})
    prefs_json = json.dumps(prefs)
    now = _utc_now()
    with _connect(cfg) as conn:
        if cfg.engine == "mysql":
            _execute(
                conn,
                """
                INSERT INTO agent_user_profile (user_id, default_company, industry, preferences, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                  default_company = VALUES(default_company),
                  industry = VALUES(industry),
                  preferences = VALUES(preferences),
                  updated_at = VALUES(updated_at)
                """,
                (user_id, company, ind, prefs_json, now),
            )
        else:
            _execute(
                conn,
                """
                INSERT INTO agent_user_profile (user_id, default_company, industry, preferences, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                  default_company = EXCLUDED.default_company,
                  industry = EXCLUDED.industry,
                  preferences = EXCLUDED.preferences,
                  updated_at = EXCLUDED.updated_at
                """,
                (user_id, company, ind, prefs_json, now),
            )
        conn.commit()
