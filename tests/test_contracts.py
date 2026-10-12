"""Validation tests for Pydantic contracts and immutability."""

import pytest
from contracts.models import (
    ContextBundle,
    LLMResponse,
    MemoryNode,
    PolicyEvaluation,
    RequestEnvelope,
    Response,
    RouteDecision,
    RuntimeResult,
    SessionState,
    SurfaceContext,
    TokenUsage,
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

    # Test TokenUsage
    usage_default = TokenUsage()
    assert usage_default.prompt_tokens == 0
    assert usage_default.completion_tokens == 0
    assert usage_default.total_tokens == 0
    assert usage_default.estimated is True

    usage_calc = TokenUsage(prompt_tokens=42, completion_tokens=18)
    assert usage_calc.prompt_tokens == 42
    assert usage_calc.completion_tokens == 18
    assert usage_calc.total_tokens == 60

    # Test ContextBundle
    bundle = ContextBundle(
        persona_prompt="You are a helpful coding assistant.",
        history=[{"turn": 1, "user": "hi"}],
        memory=[mem],
        tool_specs=[tool_spec],
        token_budget=4096,
        estimated_tokens=50,
        dropped_items=0,
        notes=["Test note"],
    )
    assert bundle.token_budget == 4096
    assert bundle.persona_prompt == "You are a helpful coding assistant."
    assert len(bundle.tool_specs) == 1
    assert bundle.estimated_tokens == 50

    # Test LLMResponse
    llm_resp_text = LLMResponse(text="Generated text", usage=usage_calc)
    assert llm_resp_text.text == "Generated text"
    assert llm_resp_text.payload == "Generated text"
    assert llm_resp_text.usage.total_tokens == 60

    llm_resp_parsed = LLMResponse(parsed={"status": "ok"})
    assert llm_resp_parsed.parsed == {"status": "ok"}
    assert llm_resp_parsed.payload == {"status": "ok"}

    # Test RuntimeResult with usage
    runtime_res = RuntimeResult(
        reply_text="Execution complete",
        usage=usage_calc,
    )
    assert runtime_res.usage.total_tokens == 60
    assert runtime_res.usage.prompt_tokens == 42

    # Test Response
    resp = Response(
        reply_text="Done",
        persona_used="coder",
        route_decision=decision,
        routing_explanation="Summoned coder because ...",
        session_id="sess-1",
        status="complete",
        usage=usage_calc,
    )
    assert resp.reply_text == "Done"
    assert resp.status == "complete"
    assert resp.pending_approval is None
    assert resp.usage.total_tokens == 60
    assert resp.usage.total_tokens == resp.usage.prompt_tokens + resp.usage.completion_tokens
