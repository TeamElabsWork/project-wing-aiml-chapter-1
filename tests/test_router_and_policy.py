"""Tests for surface policies and router behavior."""

import pytest
from contracts.models import PolicyEvaluation, RequestEnvelope, SessionState, SurfaceContext
from routing_router.mock_router import MockRouter
from routing_surface_policy.policy import SurfacePolicyEngine


def test_surface_policy_urgency_detection() -> None:
    policy = SurfacePolicyEngine("config/surfaces.yaml")
    surface_ctx = SurfaceContext(
        surface_type="slack",
        client_id="slack-1",
    )

    # Urgent message detection
    result: PolicyEvaluation = policy.evaluate(surface_ctx, "P0 incident: server is down!")
    assert result.is_urgent is True
    assert result.urgency == "high"

    # Normal message
    result_normal: PolicyEvaluation = policy.evaluate(surface_ctx, "Can you review this doc?")
    assert result_normal.is_urgent is False


@pytest.mark.asyncio
async def test_router_selects_expected_personas() -> None:
    router = MockRouter()
    surface_ctx = SurfaceContext(surface_type="cli", client_id="cli-1")
    empty_session = SessionState(session_id="s1", history=[])
    empty_policy = PolicyEvaluation(
        is_urgent=False, default_autonomy="semi", max_tokens_budget=2048
    )

    # Research query
    env_research = RequestEnvelope(
        message_id="m1",
        session_id="s1",
        user_id="u1",
        raw_text="Search recent research papers on transformer architectures",
        surface_context=surface_ctx,
    )
    decision = await router.route(env_research, empty_session, empty_policy, [])
    assert decision.persona == "researcher"

    # Ops query
    env_ops = RequestEnvelope(
        message_id="m2",
        session_id="s2",
        user_id="u1",
        raw_text="Deploy new k8s cluster version to staging",
        surface_context=surface_ctx,
    )
    decision_ops = await router.route(env_ops, empty_session, empty_policy, [])
    assert decision_ops.persona == "ops"
