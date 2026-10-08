"""Comprehensive tests for safety gating, tool execution policies, and API idempotency."""

from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock

import pytest
from api.idempotency import InMemoryIdempotencyStore
from api.main import create_app
from contracts.models import (
    ApprovalResponse,
    Response,
    RouteDecision,
    RuntimeResult,
    ToolCall,
    ToolResult,
)
from fastapi.testclient import TestClient
from orchestrator.pipeline import create_pipeline, reset_all_registries
from personas_tools_core.enforcer import ToolScopeEnforcer
from personas_tools_core.executor import ToolExecutor
from personas_tools_core.registry import ToolRegistry
from personas_tools_impl.echo_tool import register_default_tools
from routing_router.mock_router import MockRouter
from safety_approval.manager import (
    AutoApproveStub,
    DenyAllApprovalStub,
    PendingApprovalManager,
)
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
    assert result.denied is True
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
    assert result.denied is False
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


@pytest.mark.asyncio
async def test_status_derived_from_runtime_result_not_reply_text() -> None:
    """Test proves Response.status comes strictly from RuntimeResult, never from reply text."""
    pipeline = create_pipeline(config_dir="config")

    # Mock runtime to return reply text containing tricky keywords
    # but clean RuntimeResult fields
    mock_runtime = AsyncMock()
    mock_runtime.execute.return_value = RuntimeResult(
        reply_text="This text says: pending approval and approval denied!",
        tool_results=[],
        pending_approval=None,
        error=None,
    )
    pipeline.agent_runtime = mock_runtime

    resp = await pipeline.process("Do something normal")
    # Even though reply_text has 'pending approval' and 'approval denied',
    # status MUST be 'complete' because RuntimeResult has no pending/denied tools or errors.
    assert resp.status == "complete"
    assert resp.pending_approval is None

    # Now verify when RuntimeResult.error is set, status is 'error'
    mock_runtime.execute.return_value = RuntimeResult(
        reply_text="All good",
        tool_results=[],
        pending_approval=None,
        error="Runtime crashed",
    )
    resp_err = await pipeline.process("Fail please")
    assert resp_err.status == "error"

    # When tool_result has denied=True, status is 'denied'
    mock_runtime.execute.return_value = RuntimeResult(
        reply_text="Action blocked",
        tool_results=[
            ToolResult(
                call_id="c1",
                tool_name="test_tool",
                ok=False,
                output=None,
                error="Denied",
                denied=True,
            )
        ],
        pending_approval=None,
        error=None,
    )
    resp_denied = await pipeline.process("Blocked call")
    assert resp_denied.status == "denied"


@pytest.mark.asyncio
async def test_destructive_tool_gated_on_every_surface() -> None:
    """Test proves a destructive tool call is gated on telegram, slack, cli, and api surfaces."""
    surfaces = ["cli", "telegram", "slack", "api"]

    for surface in surfaces:
        pipeline = create_pipeline(
            config_dir="config",
            runtime_override="scripted",
            approval_override="pending",
        )
        resp = await pipeline.process("wipe the database cache", surface_type=surface)
        assert resp.status == "pending_approval", f"Failed on surface: {surface}"
        assert resp.pending_approval is not None
        assert resp.pending_approval.action.tool_name == "destructive_wipe"


@pytest.mark.asyncio
async def test_pending_approval_flow_approve_and_deny() -> None:
    """Test proves: pending -> approve -> executed; pending -> deny -> denied status."""
    manager = PendingApprovalManager()
    executor = ToolExecutor(
        tool_scope_enforcer=ToolScopeEnforcer(),
        risk_classifier=StubRiskClassifier(),
        approval_manager=manager,
    )

    decision = RouteDecision(
        persona="ops",
        tool_scope=["destructive_wipe"],
        autonomy="supervised",
        confidence=1.0,
        reasoning="Ops action",
    )
    call = ToolCall(
        call_id="call-deferred-01",
        tool_name="destructive_wipe",
        arguments={"target": "user_cache"},
    )

    # 1. Trigger pending execution
    result = await executor.execute(
        tool_call=call,
        decision=decision,
        caller_persona="ops",
    )
    assert result.pending is True
    assert result.ok is False

    req_id = "appr-call-deferred-01"
    pending_req = await manager.get_pending(req_id)
    assert pending_req is not None
    assert pending_req.action.tool_name == "destructive_wipe"

    # 2. Approve decision -> tool should execute
    appr_resp = ApprovalResponse(approved=True, approver="admin-user", pending=False)
    sub_res = await manager.submit_decision(req_id, appr_resp)
    assert sub_res is not None
    assert sub_res.approved is True
    assert req_id in manager.execution_results
    assert manager.execution_results[req_id].ok is True
    assert manager.execution_results[req_id].output.get("wiped") is True

    # 3. Test Deny on a separate call
    call2 = ToolCall(
        call_id="call-deferred-02",
        tool_name="destructive_wipe",
        arguments={"target": "production_db"},
    )
    result2 = await executor.execute(
        tool_call=call2,
        decision=decision,
        caller_persona="ops",
    )
    assert result2.pending is True
    req_id2 = "appr-call-deferred-02"

    deny_resp = ApprovalResponse(approved=False, approver="security-bot", pending=False)
    sub_res2 = await manager.submit_decision(req_id2, deny_resp)
    assert sub_res2 is not None
    assert sub_res2.approved is False
    assert manager.execution_results[req_id2].ok is False
    assert manager.execution_results[req_id2].denied is True


def test_telegram_and_slack_ingress_idempotency() -> None:
    """Test duplicate Telegram update_id and Slack event_id run the pipeline once."""
    mock_pipeline = AsyncMock()
    mock_pipeline.process.return_value = Response(
        reply_text="Webhook processed",
        persona_used="coder",
        route_decision=RouteDecision(
            persona="coder",
            tool_scope=[],
            autonomy="semi",
            confidence=0.9,
            reasoning="Test",
        ),
        routing_explanation="Test explanation",
        session_id="test-session",
        status="complete",
    )

    app = create_app(pipeline=mock_pipeline)
    client = TestClient(app)

    # 1. Telegram duplicate update_id test
    tg_payload = {
        "update_id": 888123,
        "message": {
            "message_id": 1,
            "text": "Hello Telegram bot",
            "from": {"id": 12345},
            "chat": {"id": 67890},
        },
    }

    res_tg1 = client.post("/v1/webhooks/telegram", json=tg_payload)
    assert res_tg1.status_code == 200
    assert mock_pipeline.process.call_count == 1

    # Sending same update_id should NOT call pipeline again
    res_tg2 = client.post("/v1/webhooks/telegram", json=tg_payload)
    assert res_tg2.status_code == 200
    assert res_tg2.headers.get("X-Idempotent-Replay") == "true"
    assert mock_pipeline.process.call_count == 1  # Still 1!

    # 2. Slack duplicate event_id test
    slack_payload = {
        "event_id": "Ev12345678",
        "event": {
            "text": "Hello Slack bot",
            "user": "U1234",
            "channel": "C5678",
        },
    }

    res_sl1 = client.post("/v1/webhooks/slack", json=slack_payload)
    assert res_sl1.status_code == 200
    assert mock_pipeline.process.call_count == 2  # Incremented once for Slack

    # Sending same event_id should NOT call pipeline again
    res_sl2 = client.post("/v1/webhooks/slack", json=slack_payload)
    assert res_sl2.status_code == 200
    assert res_sl2.headers.get("X-Idempotent-Replay") == "true"
    assert mock_pipeline.process.call_count == 2  # Still 2!


def test_config_precedence_models_yaml_honored_when_pipeline_yaml_unset(
    tmp_path: Path,
) -> None:
    """Test: setting models.yaml router.provider = 'mock' is honored when pipeline.yaml says unset."""
    reset_all_registries()

    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()

    # pipeline.yaml sets router to unset
    pipeline_yaml = cfg_dir / "pipeline.yaml"
    pipeline_yaml.write_text(
        """
backends:
  router: "unset"
""",
        encoding="utf-8",
    )

    # models.yaml sets router provider to mock
    models_yaml = cfg_dir / "models.yaml"
    models_yaml.write_text(
        """
router:
  provider: "mock"
""",
        encoding="utf-8",
    )

    pipeline = create_pipeline(config_dir=cfg_dir)
    # Pipeline should have resolved router to MockRouter
    assert isinstance(pipeline.router, MockRouter)
