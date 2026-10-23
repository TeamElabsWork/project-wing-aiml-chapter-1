"""Session state management module.

Owner: B3

Provides a ``SessionManager`` protocol, three concrete backends
(in-memory, Redis, PostgreSQL), TTL-based inactivity expiration,
and a sliding conversation window to bound prompt size.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol

from contracts.models import SessionState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults (overridable via env vars)
# ---------------------------------------------------------------------------
DEFAULT_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "2700"))  # 45 min
DEFAULT_WINDOW_SIZE: int = int(os.getenv("SESSION_WINDOW_SIZE", "20"))


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
class SessionManager(Protocol):
    """Protocol for persisting and retrieving active session interaction state."""

    async def get_session(self, session_id: str) -> SessionState:
        """Fetch session state by session ID."""
        ...

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Update arbitrary key-values on a session."""
        ...

    async def append_turn(
        self,
        session_id: str,
        user_text: str,
        persona: str,
        reply_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an interaction turn to the session history."""
        ...

    async def delete_session(self, session_id: str) -> None:
        """Delete a session, forcing a fresh state on next access."""
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_utc() -> datetime:
    """Return the current UTC-aware datetime."""
    return datetime.now(timezone.utc)


def _is_expired(last_activity_iso: str, ttl_seconds: int) -> bool:
    """Return True if the session has been idle longer than *ttl_seconds*."""
    try:
        last_dt = datetime.fromisoformat(last_activity_iso)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        elapsed = (_now_utc() - last_dt).total_seconds()
        return elapsed > ttl_seconds
    except (ValueError, TypeError):
        return True


def _apply_window(history: List[Dict[str, Any]], window_size: int) -> List[Dict[str, Any]]:
    """Trim *history* to the most recent *window_size* turns (sliding buffer)."""
    if window_size > 0 and len(history) > window_size:
        return history[-window_size:]
    return history


def _build_turn(
    user_text: str,
    persona: str,
    reply_text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct a single conversation turn dict."""
    return {
        "user_text": user_text,
        "persona": persona,
        "reply_text": reply_text,
        "timestamp": _now_utc().isoformat(),
        "metadata": metadata or {},
    }


def _fresh_session_data(session_id: str) -> Dict[str, Any]:
    """Return a blank session data dict."""
    return {
        "session_id": session_id,
        "created_at": _now_utc().isoformat(),
        "last_activity": _now_utc().isoformat(),
        "history": [],
        "active_persona": None,
        "metadata": {},
    }


def _session_data_to_state(session_id: str, data: Dict[str, Any]) -> SessionState:
    """Convert internal session dict to a ``SessionState`` contract."""
    return SessionState(
        session_id=session_id,
        history=list(data.get("history", [])),
        active_persona=data.get("active_persona"),
        metadata=dict(data.get("metadata", {})),
    )


# ---------------------------------------------------------------------------
# In-Memory Backend (enhanced with TTL + sliding window)
# ---------------------------------------------------------------------------
class InMemorySessionManager:
    """In-memory session manager with TTL expiration and sliding window.

    Suitable for local development, CLI usage, and unit tests.
    Sessions are lost on process restart.
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        window_size: int = DEFAULT_WINDOW_SIZE,
    ) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds
        self._window_size = window_size

    # -- Protocol methods ---------------------------------------------------

    async def get_session(self, session_id: str) -> SessionState:
        if session_id in self._sessions:
            data = self._sessions[session_id]
            if _is_expired(data.get("last_activity", ""), self._ttl_seconds):
                logger.info(
                    "Session '%s' expired (TTL=%ds). Resetting.", session_id, self._ttl_seconds
                )
                del self._sessions[session_id]

        if session_id not in self._sessions:
            self._sessions[session_id] = _fresh_session_data(session_id)

        return _session_data_to_state(session_id, self._sessions[session_id])

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        if session_id not in self._sessions:
            await self.get_session(session_id)
        sess = self._sessions[session_id]
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            sess.setdefault("metadata", {}).update(updates["metadata"])
        for k, v in updates.items():
            if k != "metadata":
                sess[k] = v
        sess["last_activity"] = _now_utc().isoformat()

    async def append_turn(
        self,
        session_id: str,
        user_text: str,
        persona: str,
        reply_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if session_id not in self._sessions:
            await self.get_session(session_id)
        sess = self._sessions[session_id]
        sess["active_persona"] = persona
        history: List[Dict[str, Any]] = sess.setdefault("history", [])
        history.append(_build_turn(user_text, persona, reply_text, metadata))
        sess["history"] = _apply_window(history, self._window_size)
        sess["last_activity"] = _now_utc().isoformat()

    async def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# ---------------------------------------------------------------------------
# Redis Backend
# ---------------------------------------------------------------------------
class RedisSessionManager:
    """Redis-backed session manager with native TTL and sliding window.

    Requires the ``redis`` optional dependency (``pip install routing-session[redis]``).
    Connects via the ``REDIS_URL`` environment variable (default ``redis://localhost:6379/0``).
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        window_size: int = DEFAULT_WINDOW_SIZE,
        key_prefix: str = "session:",
    ) -> None:
        try:
            aioredis = importlib.import_module("redis.asyncio")
        except ImportError as exc:
            raise ImportError(
                "RedisSessionManager requires the 'redis' package. "
                "Install it with: pip install routing-session[redis]"
            ) from exc

        self._url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._ttl_seconds = ttl_seconds
        self._window_size = window_size
        self._key_prefix = key_prefix
        self._redis: Any = aioredis.from_url(self._url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"{self._key_prefix}{session_id}"

    async def _read(self, session_id: str) -> Optional[Dict[str, Any]]:
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return None
        except (json.JSONDecodeError, TypeError):
            return None

    async def _write(self, session_id: str, data: Dict[str, Any]) -> None:
        data["last_activity"] = _now_utc().isoformat()
        await self._redis.set(
            self._key(session_id),
            json.dumps(data),
            ex=self._ttl_seconds,
        )

    # -- Protocol methods ---------------------------------------------------

    async def get_session(self, session_id: str) -> SessionState:
        data = await self._read(session_id)
        if data is None:
            data = _fresh_session_data(session_id)
            await self._write(session_id, data)
        return _session_data_to_state(session_id, data)

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        data = await self._read(session_id) or _fresh_session_data(session_id)
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            data.setdefault("metadata", {}).update(updates["metadata"])
        for k, v in updates.items():
            if k != "metadata":
                data[k] = v
        await self._write(session_id, data)

    async def append_turn(
        self,
        session_id: str,
        user_text: str,
        persona: str,
        reply_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        data = await self._read(session_id) or _fresh_session_data(session_id)
        data["active_persona"] = persona
        history: List[Dict[str, Any]] = data.setdefault("history", [])
        history.append(_build_turn(user_text, persona, reply_text, metadata))
        data["history"] = _apply_window(history, self._window_size)
        await self._write(session_id, data)

    async def delete_session(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))


# ---------------------------------------------------------------------------
# PostgreSQL Backend
# ---------------------------------------------------------------------------
class PostgresSessionManager:
    """PostgreSQL-backed session manager with JSONB history and TTL expiration.

    Requires the ``asyncpg`` optional dependency (``pip install routing-session[postgres]``).
    Connects via the ``DATABASE_URL`` environment variable.

    Expected table DDL (auto-created on first use via ``_ensure_table``)::

        CREATE TABLE IF NOT EXISTS sessions (
            session_id   TEXT PRIMARY KEY,
            history      JSONB NOT NULL DEFAULT '[]',
            active_persona TEXT,
            metadata     JSONB NOT NULL DEFAULT '{}',
            last_activity TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """

    _table_ready: bool = False

    def __init__(
        self,
        database_url: Optional[str] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        window_size: int = DEFAULT_WINDOW_SIZE,
        table_name: str = "sessions",
    ) -> None:
        try:
            importlib.import_module("asyncpg")
        except ImportError as exc:
            raise ImportError(
                "PostgresSessionManager requires the 'asyncpg' package. "
                "Install it with: pip install routing-session[postgres]"
            ) from exc

        self._database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://orchestrator_user:orchestrator_password@localhost:5432/orchestrator_db",
        )
        self._ttl_seconds = ttl_seconds
        self._window_size = window_size
        self._table_name = table_name
        self._pool: Any = None  # asyncpg.Pool, lazily created

    async def _get_pool(self) -> Any:
        if self._pool is None:
            asyncpg = importlib.import_module("asyncpg")
            self._pool = await asyncpg.create_pool(dsn=self._database_url, min_size=1, max_size=5)
        return self._pool

    async def _ensure_table(self) -> None:
        if PostgresSessionManager._table_ready:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    session_id    TEXT PRIMARY KEY,
                    history       JSONB NOT NULL DEFAULT '[]'::jsonb,
                    active_persona TEXT,
                    metadata      JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    last_activity TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
        PostgresSessionManager._table_ready = True

    # -- Protocol methods ---------------------------------------------------

    async def get_session(self, session_id: str) -> SessionState:
        await self._ensure_table()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._table_name} WHERE session_id = $1",
                session_id,
            )

        if row is not None:
            last_activity = row["last_activity"]
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            elapsed = (_now_utc() - last_activity).total_seconds()
            if elapsed > self._ttl_seconds:
                logger.info(
                    "Session '%s' expired (TTL=%ds, idle=%.0fs). Deleting.",
                    session_id,
                    self._ttl_seconds,
                    elapsed,
                )
                await self.delete_session(session_id)
                row = None

        if row is None:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (session_id, history, active_persona, metadata, last_activity)
                    VALUES ($1, $2::jsonb, $3, $4::jsonb, $5)
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    session_id,
                    "[]",
                    None,
                    "{}",
                    _now_utc(),
                )
            return SessionState(session_id=session_id, history=[], active_persona=None, metadata={})

        history_raw = row["history"]
        history = json.loads(history_raw) if isinstance(history_raw, str) else history_raw
        metadata_raw = row["metadata"]
        meta = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw

        return SessionState(
            session_id=session_id,
            history=list(history) if history else [],
            active_persona=row["active_persona"],
            metadata=dict(meta) if meta else {},
        )

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        await self._ensure_table()
        # Ensure session exists first
        await self.get_session(session_id)
        pool = await self._get_pool()

        set_clauses: List[str] = ["last_activity = now()"]
        params: List[Any] = []
        idx = 1

        if "active_persona" in updates:
            idx += 1
            set_clauses.append(f"active_persona = ${idx}")
            params.append(updates["active_persona"])
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            idx += 1
            set_clauses.append(f"metadata = metadata || ${idx}::jsonb")
            params.append(json.dumps(updates["metadata"]))

        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE {self._table_name} SET {', '.join(set_clauses)} WHERE session_id = $1",
                session_id,
                *params,
            )

    async def append_turn(
        self,
        session_id: str,
        user_text: str,
        persona: str,
        reply_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._ensure_table()
        # Ensure session exists first
        await self.get_session(session_id)
        pool = await self._get_pool()

        turn = _build_turn(user_text, persona, reply_text, metadata)

        async with pool.acquire() as conn:
            # Append turn, then trim to window_size keeping most recent
            await conn.execute(
                f"""
                UPDATE {self._table_name}
                SET history = (
                        SELECT jsonb_agg(elem)
                        FROM (
                            SELECT elem
                            FROM jsonb_array_elements(history || $2::jsonb) WITH ORDINALITY AS t(elem, ord)
                            ORDER BY ord DESC
                            LIMIT $3
                        ) sub
                        ORDER BY (sub.elem ->> 'timestamp') ASC
                    ),
                    active_persona = $4,
                    last_activity = now()
                WHERE session_id = $1
                """,
                session_id,
                json.dumps(turn),
                self._window_size,
                persona,
            )

    async def delete_session(self, session_id: str) -> None:
        await self._ensure_table()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"DELETE FROM {self._table_name} WHERE session_id = $1",
                session_id,
            )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class SessionManagerRegistry:
    """Registry allowing session manager implementations to be registered and selected via config."""

    _registry: Dict[str, Callable[..., SessionManager]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., SessionManager]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> SessionManager:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"SessionManager '{name}' not found in registry. "
                f"Registered backends: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        cls.register("in_memory", lambda **kwargs: InMemorySessionManager(**kwargs))
        cls.register("default", lambda **kwargs: InMemorySessionManager(**kwargs))
        cls.register("unset", lambda **kwargs: InMemorySessionManager(**kwargs))
        cls.register("redis", lambda **kwargs: RedisSessionManager(**kwargs))
        cls.register("postgres", lambda **kwargs: PostgresSessionManager(**kwargs))
