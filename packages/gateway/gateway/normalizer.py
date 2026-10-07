"""Gateway module for normalizing surface events into canonical RequestEnvelope instances.

Owner: A3
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Protocol

from contracts.models import RequestEnvelope, SurfaceContext


class EventNormalizer(Protocol):
    """Protocol for transforming raw surface inputs into normalized RequestEnvelopes."""

    def normalize(
        self,
        raw_input: Any,
        surface_type: str,
        user_id: str,
        session_id: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> RequestEnvelope:
        """Normalize raw input into a RequestEnvelope."""
        ...


class DefaultEventNormalizer:
    """Default working stub normalizer.

    Handles text strings, dictionary payloads, or adapter inputs and converts them
    into a canonical RequestEnvelope.
    """

    def normalize(
        self,
        raw_input: Any,
        surface_type: str,
        user_id: str,
        session_id: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> RequestEnvelope:
        # TODO (A3 Gateway Owner): Add richer surface payload unpacking,
        # media parsing (attachments/audio/images), and header extraction.
        meta = dict(metadata or {})
        text_content: str = ""

        if isinstance(raw_input, str):
            text_content = raw_input
        elif isinstance(raw_input, dict):
            text_content = str(raw_input.get("text", raw_input.get("message", "")))
            meta.update({k: v for k, v in raw_input.items() if k not in ("text", "message")})
        else:
            text_content = str(raw_input)

        active_session = session_id or f"sess-{uuid.uuid4().hex[:8]}"
        surface_ctx = SurfaceContext(
            surface_type=surface_type,
            client_id=meta.get("client_id", f"{surface_type}-client"),
            channel_id=meta.get("channel_id"),
            is_interactive=meta.get("is_interactive", True),
            supports_markdown=meta.get("supports_markdown", surface_type != "telegram"),
            urgency_hint=meta.get("urgency_hint"),
            metadata=meta,
        )

        return RequestEnvelope(
            message_id=f"msg-{uuid.uuid4().hex[:12]}",
            session_id=active_session,
            user_id=user_id,
            raw_text=text_content,
            surface_context=surface_ctx,
            metadata=meta,
            timestamp=datetime.now(timezone.utc),
        )
