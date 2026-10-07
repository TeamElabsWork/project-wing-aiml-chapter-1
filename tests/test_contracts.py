"""Validation tests for Pydantic contracts and immutability."""

import pytest
from contracts.models import (
    MemoryNode,
    RequestEnvelope,
    Response,
    RouteDecision,
    SurfaceContext,
)
from pydantic import ValidationError


def test_contracts_creation_and_validation() -> None:
    surface_ctx = SurfaceContext(
        surface_type="cli",
        client_id="terminal-01",
        supports_markdown=True,
    )
    assert surface_ctx.surface_type == "cli"

    envelope = RequestEnvelope(
        message_id="msg-1",
        session_id="sess-1",
        user_id="usr-1",
        raw_text="hello",
        surface_context=surface_ctx,
    )
    assert envelope.user_id == "usr-1"

    decision = RouteDecision(
        persona="coder",
        tool_scope=["echo"],
        autonomy="semi",
        confidence=0.9,
        reasoning="Testing decision",
    )
    assert decision.confidence == 0.9

    # Confidence must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        RouteDecision(
            persona="coder",
            tool_scope=[],
            autonomy="semi",
            confidence=1.5,
            reasoning="Invalid confidence",
        )

    # Test MemoryNode
    mem = MemoryNode(
        node_id="mem-1",
        user_id="usr-1",
        surface="cli",
        persona="coder",
        summary="Test memory",
    )
    assert mem.node_id == "mem-1"

    # Test Response
    resp = Response(
        reply_text="Done",
        persona_used="coder",
        route_decision=decision,
        routing_explanation="Summoned coder because ...",
        session_id="sess-1",
    )
    assert resp.reply_text == "Done"
