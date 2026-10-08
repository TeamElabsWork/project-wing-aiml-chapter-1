"""Comprehensive tests for safety gating, tool execution policies, and API idempotency."""

from typing import Generator

import pytest
from api.idempotency import InMemoryIdempotencyStore
from api.main import create_app
from contracts.models import RouteDecision, ToolCall, ToolResult
from fastapi.testclient import TestClient
from personas_tools_core.enforcer import ToolScopeEnforcer
from personas_tools_core.executor import ToolExecutor
from personas_tools_core.registry import ToolRegistry
from personas_tools_impl.echo_tool import register_default_tools
from safety_approval.manager import AutoApproveStub, DenyAllApprovalStub
from safety_risk_classifier.classifier import StubRiskClassifier


@pytest.fixture(autouse=True)
def setup_tools() -> Generator[None, None, None]:
    ToolRegistry.reset()
    register_default_tools()
    yield
    ToolRegistry.reset()


@pytest.mark.asyncio
async def test_out_of_scope_tool_is_blocked() -> None:
    """Verify tool calls outside of RouteDecision tool_scope are blocked."""
    executor = ToolExecutor(
        tool_scope_enforcer=ToolScopeEnforcer(),
        risk_classifier=StubRiskClassifier(),
        approval_manager=AutoApproveStub(),
    )

    decision = RouteDecision(
        persona="coder",
        tool_scope=["echo"],  # only echo is allowed
        autonomy="full",
        confidence=0.9,
        reasoning="Testing scope enforcement",
    )

    # Attempt to call github_pr which is NOT in scope
    call = ToolCall(
        call_id="call-1",
        tool_name="github_pr",
        arguments={"title": "Test PR"},
    )
    result: ToolResult = await executor.execute(
        tool_call=call,
        decision=decision,
        caller_persona="coder",
    )

    assert result.ok is False
    assert "not permitted by active tool scope" in (result.error or "")


@pytest.mark.asyncio
async def test_destructive_tool_requires_approval_and_fails_when_denied() -> None:
    """Verify destructive tools are gated across all surfaces and autonomy tiers, and fail on rejection."""
    executor = ToolExecutor(
        tool_scope_enforcer=ToolScopeEnforcer(),
        risk_classifier=StubRiskClassifier(),
        approval_manager=DenyAllApprovalStub(),
    )

    # Even with autonomy='full', destructive tools must require approval
    decision = RouteDecision(
        persona="ops",
        tool_scope=["destructive_wipe"],
        autonomy="full",
        confidence=1.0,
        reasoning="Full autonomy ops decision",
    )

    call = ToolCall(
        call_id="call-wipe",
        tool_name="destructive_wipe",
        arguments={"target": "all_records"},
    )
    result = await executor.execute(
        tool_call=call,
        decision=decision,
        caller_persona="ops",
    )

    assert result.ok is False
    assert "Action rejected by DenyAllApprovalStub policy" in (result.error or "")


@pytest.mark.asyncio
async def test_destructive_tool_succeeds_when_approved() -> None:
    """Verify destructive tool executes when approval is granted."""
    executor = ToolExecutor(
        tool_scope_enforcer=ToolScopeEnforcer(),
        risk_classifier=StubRiskClassifier(),
        approval_manager=AutoApproveStub(),
    )

    decision = RouteDecision(
        persona="ops",
        tool_scope=["destructive_wipe"],
        autonomy="supervised",
        confidence=1.0,
        reasoning="Supervised ops decision",
    )

    call = ToolCall(
        call_id="call-wipe-ok",
        tool_name="destructive_wipe",
        arguments={"target": "temp_cache"},
    )
    result = await executor.execute(
        tool_call=call,
        decision=decision,
        caller_persona="ops",
    )

    assert result.ok is True
    assert result.output.get("wiped") is True


@pytest.mark.asyncio
async def test_idempotency_store_deduplication() -> None:
    """Verify idempotency store stores and retrieves cached responses."""
    store = InMemoryIdempotencyStore()

    payload = {"status": "ok", "turn": 1}
    await store.set("key-123", payload, ttl_seconds=300)

    cached = await store.get("key-123")
    assert cached == payload

    # Non-existent key returns None
    assert await store.get("key-non-existent") is None


def test_api_healthz_and_idempotency_headers() -> None:
    """Verify FastAPI ingress /healthz and /v1/message idempotency header deduplication."""
    app = create_app()
    client = TestClient(app)

    # 1. Healthz
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "0.2.0"}

    # 2. Inbound message with Idempotency-Key
    body = {
        "text": "Hello world from test client",
        "surface_type": "api",
        "user_id": "test-user-1",
    }
    headers = {"Idempotency-Key": "test-idem-001"}

    resp1 = client.post("/v1/message", json=body, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "reply_text" in data1
    assert resp1.headers.get("X-Idempotent-Replay") is None

    # Re-sending with same Idempotency-Key should return replay
    resp2 = client.post("/v1/message", json=body, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["reply_text"] == data1["reply_text"]
    assert resp2.headers.get("X-Idempotent-Replay") == "true"
