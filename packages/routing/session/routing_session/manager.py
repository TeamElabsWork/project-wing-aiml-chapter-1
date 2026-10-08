"""Session state management module.

Owner: B3
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol

from contracts.models import SessionState


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


class InMemorySessionManager:
    """In-memory stub implementation of SessionManager."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}

    async def get_session(self, session_id: str) -> SessionState:
        # TODO (B3 Session Owner): Replace with Redis / database persistent store,
        # session windowing, and summarization triggers.
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "history": [],
                "active_persona": None,
                "metadata": {},
            }
        data = self._sessions[session_id]
        return SessionState(
            session_id=session_id,
            history=list(data.get("history", [])),
            active_persona=data.get("active_persona"),
            metadata=dict(data.get("metadata", {})),
        )

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        if session_id not in self._sessions:
            await self.get_session(session_id)
        sess = self._sessions[session_id]
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            sess.setdefault("metadata", {}).update(updates["metadata"])
        for k, v in updates.items():
            if k != "metadata":
                sess[k] = v

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
        history.append(
            {
                "user_text": user_text,
                "persona": persona,
                "reply_text": reply_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {},
            }
        )


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
                f"SessionManager '{name}' not found in registry. Registered backends: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        cls.register("in_memory", lambda **kwargs: InMemorySessionManager())
        cls.register("default", lambda **kwargs: InMemorySessionManager())


# Register defaults
SessionManagerRegistry.register_defaults()
