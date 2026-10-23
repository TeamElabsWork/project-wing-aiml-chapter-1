"""Tests for routing-session (B3) — TTL expiration, sliding window, and registry.

All tests run offline using only the InMemorySessionManager.
Redis and PostgreSQL backends are tested for import-guarding only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator
from unittest.mock import patch

import pytest
from contracts.models import SessionState
from routing_session.manager import (
    DEFAULT_TTL_SECONDS,
    DEFAULT_WINDOW_SIZE,
    InMemorySessionManager,
    PostgresSessionManager,
    RedisSessionManager,
    SessionManagerRegistry,
    _apply_window,
    _build_turn,
    _fresh_session_data,
    _is_expired,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def mgr() -> InMemorySessionManager:
    """Session manager with short TTL for testing."""
    return InMemorySessionManager(ttl_seconds=60, window_size=5)


@pytest.fixture(autouse=True)
def _reset_registry() -> Generator[None, None, None]:
    """Ensure a clean registry for every test."""
    SessionManagerRegistry.reset()
    SessionManagerRegistry.register_defaults()
    yield
    SessionManagerRegistry.reset()


# ---------------------------------------------------------------------------
# Pure helper unit tests
# ---------------------------------------------------------------------------
class TestHelpers:
    """Tests for module-level helper functions."""

    def test_is_expired_true(self) -> None:
        old = "2020-01-01T00:00:00+00:00"
        assert _is_expired(old, ttl_seconds=60) is True

    def test_is_expired_false(self) -> None:
        recent = datetime.now(timezone.utc).isoformat()
        assert _is_expired(recent, ttl_seconds=9999) is False

    def test_is_expired_bad_value(self) -> None:
        assert _is_expired("not-a-date", ttl_seconds=60) is True

    def test_apply_window_trims(self) -> None:
        history = [{"i": i} for i in range(10)]
        trimmed = _apply_window(history, window_size=3)
        assert len(trimmed) == 3
        assert trimmed[0]["i"] == 7

    def test_apply_window_no_trim_needed(self) -> None:
        history = [{"i": i} for i in range(3)]
        assert _apply_window(history, window_size=5) is history  # same reference

    def test_build_turn_structure(self) -> None:
        turn = _build_turn("hello", "coder", "hi back", {"extra": True})
        assert turn["user_text"] == "hello"
        assert turn["persona"] == "coder"
        assert turn["reply_text"] == "hi back"
        assert turn["metadata"] == {"extra": True}
        assert "timestamp" in turn

    def test_fresh_session_data_keys(self) -> None:
        data = _fresh_session_data("s1")
        assert data["session_id"] == "s1"
        assert data["history"] == []
        assert data["active_persona"] is None
        assert "last_activity" in data
        assert "created_at" in data


# ---------------------------------------------------------------------------
# InMemorySessionManager tests
# ---------------------------------------------------------------------------
class TestInMemorySessionManager:
    """Core tests for the in-memory backend."""

    @pytest.mark.asyncio
    async def test_get_session_creates_fresh(self, mgr: InMemorySessionManager) -> None:
        state = await mgr.get_session("new-session")
        assert isinstance(state, SessionState)
        assert state.session_id == "new-session"
        assert state.history == []
        assert state.active_persona is None

    @pytest.mark.asyncio
    async def test_append_turn_basic(self, mgr: InMemorySessionManager) -> None:
        await mgr.append_turn("s1", "hi", "coder", "hello!", {"k": "v"})
        state = await mgr.get_session("s1")
        assert len(state.history) == 1
        turn = state.history[0]
        assert turn["user_text"] == "hi"
        assert turn["persona"] == "coder"
        assert turn["reply_text"] == "hello!"
        assert turn["metadata"] == {"k": "v"}

    @pytest.mark.asyncio
    async def test_append_turn_updates_active_persona(self, mgr: InMemorySessionManager) -> None:
        await mgr.append_turn("s1", "q1", "researcher", "a1")
        state = await mgr.get_session("s1")
        assert state.active_persona == "researcher"

        await mgr.append_turn("s1", "q2", "coder", "a2")
        state = await mgr.get_session("s1")
        assert state.active_persona == "coder"

    @pytest.mark.asyncio
    async def test_sliding_window(self, mgr: InMemorySessionManager) -> None:
        # window_size=5, append 8 turns
        for i in range(8):
            await mgr.append_turn("s1", f"q{i}", "coder", f"a{i}")

        state = await mgr.get_session("s1")
        assert len(state.history) == 5
        # Oldest remaining should be turn 3
        assert state.history[0]["user_text"] == "q3"
        assert state.history[-1]["user_text"] == "q7"

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, mgr: InMemorySessionManager) -> None:
        await mgr.append_turn("s1", "q", "coder", "a")
        state = await mgr.get_session("s1")
        assert len(state.history) == 1

        # Simulate expiry by patching last_activity to a very old timestamp
        mgr._sessions["s1"]["last_activity"] = "2000-01-01T00:00:00+00:00"

        state = await mgr.get_session("s1")
        assert len(state.history) == 0  # Session was reset

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self, mgr: InMemorySessionManager) -> None:
        await mgr.append_turn("s1", "q", "coder", "a")
        # Immediately get — should NOT expire (TTL=60s)
        state = await mgr.get_session("s1")
        assert len(state.history) == 1

    @pytest.mark.asyncio
    async def test_delete_session(self, mgr: InMemorySessionManager) -> None:
        await mgr.append_turn("s1", "q", "coder", "a")
        await mgr.delete_session("s1")
        state = await mgr.get_session("s1")
        assert len(state.history) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, mgr: InMemorySessionManager) -> None:
        # Should not raise
        await mgr.delete_session("does-not-exist")

    @pytest.mark.asyncio
    async def test_update_session_metadata(self, mgr: InMemorySessionManager) -> None:
        await mgr.get_session("s1")
        await mgr.update_session("s1", {"metadata": {"key": "value"}})
        state = await mgr.get_session("s1")
        assert state.metadata.get("key") == "value"

    @pytest.mark.asyncio
    async def test_update_session_active_persona(self, mgr: InMemorySessionManager) -> None:
        await mgr.get_session("s1")
        await mgr.update_session("s1", {"active_persona": "writer"})
        state = await mgr.get_session("s1")
        assert state.active_persona == "writer"

    @pytest.mark.asyncio
    async def test_update_session_on_nonexistent_creates_it(
        self, mgr: InMemorySessionManager
    ) -> None:
        await mgr.update_session("brand-new", {"active_persona": "ops"})
        state = await mgr.get_session("brand-new")
        assert state.active_persona == "ops"

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self, mgr: InMemorySessionManager) -> None:
        await mgr.append_turn("s1", "q1", "coder", "a1")
        await mgr.append_turn("s2", "q2", "researcher", "a2")

        s1 = await mgr.get_session("s1")
        s2 = await mgr.get_session("s2")

        assert len(s1.history) == 1
        assert s1.history[0]["persona"] == "coder"
        assert len(s2.history) == 1
        assert s2.history[0]["persona"] == "researcher"


# ---------------------------------------------------------------------------
# Default config constants
# ---------------------------------------------------------------------------
class TestDefaults:
    """Verify default configuration values are sensible."""

    def test_default_ttl(self) -> None:
        assert DEFAULT_TTL_SECONDS == 2700  # 45 minutes

    def test_default_window(self) -> None:
        assert DEFAULT_WINDOW_SIZE == 20

    def test_inmemory_uses_defaults(self) -> None:
        mgr = InMemorySessionManager()
        assert mgr._ttl_seconds == DEFAULT_TTL_SECONDS
        assert mgr._window_size == DEFAULT_WINDOW_SIZE


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------
class TestSessionManagerRegistry:
    """Tests for the SessionManagerRegistry."""

    def test_get_in_memory(self) -> None:
        mgr = SessionManagerRegistry.get("in_memory")
        assert isinstance(mgr, InMemorySessionManager)

    def test_get_default(self) -> None:
        mgr = SessionManagerRegistry.get("default")
        assert isinstance(mgr, InMemorySessionManager)

    def test_get_unset(self) -> None:
        mgr = SessionManagerRegistry.get("unset")
        assert isinstance(mgr, InMemorySessionManager)

    def test_get_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="not found in registry"):
            SessionManagerRegistry.get("nonexistent-backend")

    def test_case_insensitive(self) -> None:
        mgr = SessionManagerRegistry.get("IN_MEMORY")
        assert isinstance(mgr, InMemorySessionManager)

    def test_register_custom(self) -> None:
        SessionManagerRegistry.register(
            "custom", lambda **kw: InMemorySessionManager(ttl_seconds=10)
        )
        mgr = SessionManagerRegistry.get("custom")
        assert isinstance(mgr, InMemorySessionManager)
        assert mgr._ttl_seconds == 10

    def test_reset_clears_all(self) -> None:
        SessionManagerRegistry.reset()
        with pytest.raises(KeyError):
            SessionManagerRegistry.get("default")

    def test_redis_registered(self) -> None:
        # Redis backend is registered; instantiation may fail if redis not installed
        assert "redis" in SessionManagerRegistry._registry

    def test_postgres_registered(self) -> None:
        # Postgres backend is registered; instantiation may fail if asyncpg not installed
        assert "postgres" in SessionManagerRegistry._registry


# ---------------------------------------------------------------------------
# Optional dependency guard tests
# ---------------------------------------------------------------------------
class TestOptionalDependencyGuards:
    """Verify that Redis and Postgres backends fail gracefully when deps are missing."""

    def test_redis_import_error(self) -> None:
        with patch.dict("sys.modules", {"redis": None, "redis.asyncio": None}):
            with pytest.raises(ImportError, match="redis"):
                RedisSessionManager()

    def test_postgres_import_error(self) -> None:
        with patch.dict("sys.modules", {"asyncpg": None}):
            with pytest.raises(ImportError, match="asyncpg"):
                PostgresSessionManager()
