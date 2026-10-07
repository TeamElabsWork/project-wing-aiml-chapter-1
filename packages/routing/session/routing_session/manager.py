"""Session state management module.

Owner: B3
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol


class SessionManager(Protocol):
    """Protocol for persisting and retrieving active session interaction state."""

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Fetch session state dictionary by session ID."""
        ...

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Update arbitrary key-values on a session."""
        ...

    def append_turn(
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

    def get_session(self, session_id: str) -> Dict[str, Any]:
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
        return self._sessions[session_id]

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        sess = self.get_session(session_id)
        sess.update(updates)

    def append_turn(
        self,
        session_id: str,
        user_text: str,
        persona: str,
        reply_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        sess = self.get_session(session_id)
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
