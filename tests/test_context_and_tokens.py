"""Tests for context bundle assembly, token accounting, and configuration wiring.

Tests the plumbing introduced for context quality and token efficiency.
"""

from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import pytest
import yaml
from contracts.models import (
    ContextBundle,
    MemoryNode,
    Persona,
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
from orchestrator.pipeline import create_pipeline, reset_all_registries
from personas_context_builder.base import ContextBuilderRegistry
from personas_context_builder.passthrough import PassthroughContextBuilder
from personas_tools_core.registry import ToolRegistry


class RecordingRuntime:
    """Runtime stub that captures the ContextBundle passed to execute()."""

    def __init__(self) -> None:
        self.last_context: Optional[ContextBundle] = None
        self.last_envelope: Optional[RequestEnvelope] = None

    async def execute(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        context: Optional[ContextBundle] = None,
        **kwargs: Any,
    ) -> RuntimeResult:
        self.last_context = context
        self.last_envelope = envelope
        prompt_text = envelope.raw_text + (context.persona_prompt if context else "")
        prompt_tokens = len(prompt_text) // 4
        reply_text = f"Recording response for: {envelope.raw_text}"
        completion_tokens = len(reply_text) // 4
        return RuntimeResult(
            reply_text=reply_text,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated=True,
            ),
        )

    async def stream(
        self,
        envelope: RequestEnvelope,
        decision: RouteDecision,
        persona: Persona,
        session_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        context: Optional[ContextBundle] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        res = await self.execute(
            envelope=envelope,
            decision=decision,
            persona=persona,
            session_history=session_history,
            tool_executor=tool_executor,
            context=context,
            **kwargs,
        )
        yield res.reply_text


@pytest.mark.asyncio
async def test_context_bundle_only_includes_in_scope_tools() -> None:
    """Verify ContextBundle only contains ToolSpecs allowed by decision.tool_scope."""
    ToolRegistry.reset()
    spec_echo = ToolSpec(
        name="echo",
        description="Echo input text back",
        parameters_schema={},
    )
    spec_wipe = ToolSpec(
        name="destructive_wipe",
        description="Destructive disk wipe",
        destructive=True,
    )
    ToolRegistry.register(spec_echo, lambda **kw: None)
    ToolRegistry.register(spec_wipe, lambda **kw: None)

    builder = PassthroughContextBuilder(tool_registry=ToolRegistry)

    envelope = RequestEnvelope(
        message_id="msg-1",
        session_id="sess-1",
        user_id="usr-1",
        raw_text="Echo hello",
        surface_context=SurfaceContext(surface_type="cli", client_id="c1"),
    )
    persona = Persona(
        id="coder",
        name="Coder",
        description="Writes code",
        system_prompt="You are a coder.",
        allowed_tools=["echo", "destructive_wipe"],
    )
    policy = PolicyEvaluation(max_tokens_budget=4096)
    session_state = SessionState(session_id="sess-1")

    # 1. tool_scope allows only 'echo'
    decision_echo = RouteDecision(
        persona="coder",
        tool_scope=["echo"],
        autonomy="semi",
        urgency="normal",
        confidence=0.9,
        reasoning="Only echo permitted",
    )
    bundle_echo = await builder.build(
        envelope=envelope,
        decision=decision_echo,
        persona=persona,
        policy=policy,
        session_state=session_state,
        memory=[],
    )
    assert len(bundle_echo.tool_specs) == 1
    assert bundle_echo.tool_specs[0].name == "echo"

    # 2. tool_scope allows both tools
    decision_both = RouteDecision(
        persona="coder",
        tool_scope=["echo", "destructive_wipe"],
        autonomy="supervised",
        urgency="high",
        confidence=0.9,
        reasoning="Both tools permitted",
    )
    bundle_both = await builder.build(
        envelope=envelope,
        decision=decision_both,
        persona=persona,
        policy=policy,
        session_state=session_state,
        memory=[],
    )
    assert len(bundle_both.tool_specs) == 2
    tool_names = {s.name for s in bundle_both.tool_specs}
    assert tool_names == {"echo", "destructive_wipe"}

    # 3. tool_scope is empty
    decision_none = RouteDecision(
        persona="coder",
        tool_scope=[],
        autonomy="read_only",
        urgency="normal",
        confidence=0.9,
        reasoning="No tools permitted",
    )
    bundle_none = await builder.build(
        envelope=envelope,
        decision=decision_none,
        persona=persona,
        policy=policy,
        session_state=session_state,
        memory=[],
    )
    assert len(bundle_none.tool_specs) == 0


@pytest.mark.asyncio
async def test_runtime_receives_surface_token_budget() -> None:
    """Verify runtime receives a ContextBundle whose token_budget matches the surface's budget.

    Tests two surfaces with distinct budgets from config/surfaces.yaml:
    CLI (budget: 4096) and Telegram (budget: 1024).
    """
    pipeline = create_pipeline(config_dir="config")
    recording_runtime = RecordingRuntime()
    pipeline.agent_runtime = recording_runtime

    # Test Surface 1: CLI (configured with 4096 tokens in config/surfaces.yaml, or 1024 after-hours)
    await pipeline.process(
        raw_input="Investigate high CPU usage",
        surface_type="cli",
        session_id="test-cli-sess",
    )
    assert recording_runtime.last_context is not None
    assert recording_runtime.last_context.token_budget in (4096, 1024)

    # Test Surface 2: Telegram (configured with 1024 tokens in config/surfaces.yaml, or 512 after-hours)
    await pipeline.process(
        raw_input="Check server status",
        surface_type="telegram",
        session_id="test-tg-sess",
    )
    assert recording_runtime.last_context is not None
    assert recording_runtime.last_context.token_budget in (1024, 512)


@pytest.mark.asyncio
async def test_retrieved_memory_reaches_runtime() -> None:
    """Verify retrieved cross-surface memory reaches the agent runtime in ContextBundle."""
    pipeline = create_pipeline(config_dir="config")
    recording_runtime = RecordingRuntime()
    pipeline.agent_runtime = recording_runtime

    user_id = pipeline.identity_resolver.resolve_user(surface="cli", external_id="local-user")
    sample_mem = MemoryNode(
        node_id="mem-target-99",
        user_id=user_id,
        surface="cli",
        project_tag="auth-service",
        persona="coder",
        summary="User preferred async/await syntax over promise chains.",
    )
    await pipeline.memory_repo.save(sample_mem)

    # Inbound message from local-user
    await pipeline.process(
        raw_input="Refactor auth service handlers",
        surface_type="cli",
        external_user_id="local-user",
        session_id="test-mem-sess",
        metadata={"project_tag": "auth-service"},
    )

    # Assert retrieved memory was injected into ContextBundle delivered to the runtime
    assert recording_runtime.last_context is not None
    memories = recording_runtime.last_context.memory
    assert len(memories) >= 1
    summaries = [m.summary for m in memories]
    assert any("async/await syntax" in s for s in summaries)


@pytest.mark.asyncio
async def test_memory_retrieval_limit_read_from_config(tmp_path: Path) -> None:
    """Verify memory retrieval limit is read from pipeline.yaml limits.memory_retrieval_limit."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create surfaces.yaml
    with open("config/surfaces.yaml", "r", encoding="utf-8") as f:
        surfaces_content = f.read()
    with open(config_dir / "surfaces.yaml", "w", encoding="utf-8") as f:
        f.write(surfaces_content)

    # Create pipeline.yaml with custom limit: 7
    pipeline_cfg = {
        "version": "1.0",
        "backends": {
            "router": "mock",
            "runtime": "echo",
            "context_builder": "default",
        },
        "limits": {
            "memory_retrieval_limit": 7,
        },
    }
    with open(config_dir / "pipeline.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(pipeline_cfg, f)

    pipeline = create_pipeline(config_dir=config_dir)
    assert pipeline.memory_retrieval_limit == 7

    # Verify retrieval limit was actually used during process
    call_limits: List[int] = []
    original_retrieve = pipeline.memory_retriever.retrieve

    async def spy_retrieve(*args: Any, **kwargs: Any) -> List[MemoryNode]:
        call_limits.append(kwargs.get("limit", 0))
        return await original_retrieve(*args, **kwargs)

    pipeline.memory_retriever.retrieve = spy_retrieve  # type: ignore[method-assign]

    await pipeline.process(raw_input="List pending pull requests", surface_type="cli")
    assert call_limits == [7]


@pytest.mark.asyncio
async def test_response_usage_populated_and_consistent() -> None:
    """Verify Response.usage is populated and total_tokens == prompt_tokens + completion_tokens."""
    pipeline = create_pipeline(config_dir="config")
    response: Response = await pipeline.process(
        raw_input="Implement binary search algorithm in Python",
        surface_type="cli",
    )

    assert response.usage is not None
    assert response.usage.prompt_tokens > 0
    assert response.usage.completion_tokens > 0
    assert (
        response.usage.total_tokens
        == response.usage.prompt_tokens + response.usage.completion_tokens
    )
    assert response.usage.estimated is True


@pytest.mark.asyncio
async def test_custom_context_builder_in_pipeline_yaml_honored(tmp_path: Path) -> None:
    """Verify configuring context_builder in pipeline.yaml is honored."""
    reset_all_registries()

    class CustomMarkerContextBuilder:
        async def build(
            self,
            envelope: RequestEnvelope,
            decision: RouteDecision,
            persona: Persona,
            policy: PolicyEvaluation,
            session_state: SessionState,
            memory: List[MemoryNode],
            **kwargs: Any,
        ) -> ContextBundle:
            return ContextBundle(
                persona_prompt="Custom marker prompt",
                token_budget=9999,
                notes=["CustomMarkerContextBuilder applied"],
            )

    ContextBuilderRegistry.register("custom_marker", lambda **kwargs: CustomMarkerContextBuilder())

    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create pipeline.yaml specifying context_builder: "custom_marker"
    pipeline_cfg = {
        "version": "1.0",
        "backends": {
            "context_builder": "custom_marker",
        },
    }
    with open(config_dir / "pipeline.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(pipeline_cfg, f)

    pipeline = create_pipeline(config_dir=config_dir)
    assert isinstance(pipeline.context_builder, CustomMarkerContextBuilder)

    # Process and verify the custom context bundle reached runtime
    recording_runtime = RecordingRuntime()
    pipeline.agent_runtime = recording_runtime

    await pipeline.process(raw_input="Hello custom builder", surface_type="cli")
    assert recording_runtime.last_context is not None
    assert recording_runtime.last_context.token_budget == 9999
    assert recording_runtime.last_context.persona_prompt == "Custom marker prompt"
    assert "CustomMarkerContextBuilder applied" in recording_runtime.last_context.notes


@pytest.mark.asyncio
async def test_mock_llm_provider_returns_llm_response() -> None:
    """Verify MockLLMProvider.complete() and structured() return LLMResponse with TokenUsage."""
    from personas_runtime.mock_llm import MockLLMProvider

    provider = MockLLMProvider()
    resp = await provider.complete("Hello world", system="You are an assistant.")
    assert resp.text is not None
    assert resp.payload == resp.text
    assert resp.usage.prompt_tokens > 0
    assert resp.usage.completion_tokens > 0
    assert resp.usage.total_tokens == resp.usage.prompt_tokens + resp.usage.completion_tokens
    assert resp.usage.estimated is True

    structured_resp = await provider.structured("Create route", schema=RouteDecision)
    assert structured_resp.parsed is not None
    assert structured_resp.usage.total_tokens == (
        structured_resp.usage.prompt_tokens + structured_resp.usage.completion_tokens
    )
