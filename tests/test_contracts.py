"""Validation tests for Pydantic contracts and immutability."""

import pytest
from contracts.models import (
    MemoryNode,
    PolicyEvaluation,
    RequestEnvelope,
    Response,
    RouteDecision,
    SessionState,
    SurfaceContext,
    ToolSpec,
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
        urgency="normal",
        confidence=0.9,
        reasoning="Testing decision",
    )
    assert decision.confidence == 0.9
    assert decision.urgency == "normal"

    # Confidence must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        RouteDecision(
            persona="coder",
            tool_scope=[],
            autonomy="semi",
            confidence=1.5,
            reasoning="Invalid confidence",
        )

    # Test PolicyEvaluation
    policy_eval = PolicyEvaluation(
        is_urgent=True,
        urgency="high",
        default_autonomy="supervised",
        max_tokens_budget=1024,
    )
    assert policy_eval.urgency == "high"
    assert policy_eval.default_autonomy == "supervised"

    # Test SessionState
    session_state = SessionState(
        session_id="sess-1",
        history=[{"turn": 1, "user": "hi"}],
    )
    assert session_state.session_id == "sess-1"
    assert len(session_state.history) == 1

    # Test ToolSpec extensions
    tool_spec = ToolSpec(
        name="test_tool",
        description="A test tool",
        parameters_schema={"type": "object"},
        destructive=True,
        side_effects="write",
        execution_target="local",
    )
    assert tool_spec.destructive is True
    assert tool_spec.side_effects == "write"

    # Test MemoryNode
    mem = MemoryNode(
        node_id="mem-1",
        user_id="usr-1",
        surface="cli",
        project_tag="wing-project",
        persona="coder",
        summary="Test memory",
    )
    assert mem.node_id == "mem-1"
    assert mem.project_tag == "wing-project"

    # Test Response
    resp = Response(
        reply_text="Done",
        persona_used="coder",
        route_decision=decision,
        routing_explanation="Summoned coder because ...",
        session_id="sess-1",
        status="complete",
    )
    assert resp.reply_text == "Done"
    assert resp.status == "complete"
    assert resp.pending_approval is None
