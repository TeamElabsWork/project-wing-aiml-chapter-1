"""End-to-end orchestration pipeline wiring all modular packages together.

Wires Gateway -> Identity -> Policy -> Router -> Persona -> Runtime -> Safety -> Memory -> RoutingLog.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

import yaml
from contracts.models import RequestEnvelope, Response, ResponseStatus, RouteDecision, RuntimeResult
from gateway.normalizer import DefaultEventNormalizer, EventNormalizer
from identity.resolver import IdentityResolver, IdentityResolverRegistry
from memory_retriever.retriever import MemoryRetriever, MemoryRetrieverRegistry
from memory_store.base import MemoryRepository, MemoryStoreRegistry
from memory_store.embeddings import EmbeddingProviderRegistry
from memory_writer.writer import MemoryWriter, MemoryWriterRegistry
from personas_registry.registry import PersonaRegistry
from personas_runtime.base import AgentRuntime, LLMProviderRegistry, RuntimeRegistry
from personas_tools_core.enforcer import ToolScopeEnforcer
from personas_tools_core.executor import ToolExecutor
from personas_tools_core.registry import ToolRegistry
from routing_router.base import Router, RouterRegistry
from routing_session.manager import SessionManager, SessionManagerRegistry
from routing_surface_policy.policy import (
    SurfacePolicyProtocol,
    SurfacePolicyRegistry,
)
from safety_approval.manager import ApprovalManager, ApprovalManagerRegistry
from safety_risk_classifier.classifier import RiskClassifier, RiskClassifierRegistry
from transparency_routing_log.logger import RoutingLogger, RoutingLoggerProtocol

logger = logging.getLogger(__name__)


def _is_set(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str) and (val.strip() == "" or val.strip().lower() == "unset"):
        return False
    return True


def _resolve_backend(
    registry: Any,
    configured_name: Optional[str],
    component_name: str,
    default_name: str = "default",
    **kwargs: Any,
) -> Any:
    target = configured_name if _is_set(configured_name) else default_name
    if not _is_set(configured_name):
        logger.info(
            "Pipeline component '%s' is unset in config. Using fallback '%s'.",
            component_name,
            target,
        )
    try:
        return registry.get(target, **kwargs)
    except KeyError:
        logger.warning(
            "Backend '%s' for component '%s' not registered. Falling back to '%s'.",
            target,
            component_name,
            default_name,
        )
        return registry.get(default_name, **kwargs)


def register_all_defaults(config_dir: Optional[Path | str] = None) -> None:
    """Register default implementations across all subsystem registries."""
    cfg_path = Path(config_dir) if config_dir else Path("config")
    surfaces_cfg = cfg_path / "surfaces.yaml"

    IdentityResolverRegistry.register_defaults()
    SurfacePolicyRegistry.register_defaults(
        config_path=surfaces_cfg if surfaces_cfg.exists() else None
    )
    SessionManagerRegistry.register_defaults()
    RouterRegistry.register_defaults()
    RuntimeRegistry.register_defaults()
    LLMProviderRegistry.register_defaults()
    ToolRegistry.register_defaults()
    RiskClassifierRegistry.register_defaults()
    ApprovalManagerRegistry.register_defaults()
    EmbeddingProviderRegistry.register_defaults()
    MemoryStoreRegistry.register_defaults()
    MemoryWriterRegistry.register_defaults()
    MemoryRetrieverRegistry.register_defaults()


def reset_all_registries() -> None:
    """Reset all subsystem registries. Useful for test isolation."""
    IdentityResolverRegistry.reset()
    SurfacePolicyRegistry.reset()
    SessionManagerRegistry.reset()
    RouterRegistry.reset()
    RuntimeRegistry.reset()
    LLMProviderRegistry.reset()
    ToolRegistry.reset()
    RiskClassifierRegistry.reset()
    ApprovalManagerRegistry.reset()
    EmbeddingProviderRegistry.reset()
    MemoryStoreRegistry.reset()
    MemoryWriterRegistry.reset()
    MemoryRetrieverRegistry.reset()


reset = reset_all_registries


class OrchestratorPipeline:
    """The central orchestrator coordinating request flow across all system boundaries."""

    def __init__(
        self,
        normalizer: EventNormalizer,
        identity_resolver: IdentityResolver,
        surface_policy: SurfacePolicyProtocol,
        router: Router,
        session_manager: SessionManager,
        persona_registry: PersonaRegistry,
        agent_runtime: AgentRuntime,
        risk_classifier: RiskClassifier,
        approval_manager: ApprovalManager,
        memory_repo: MemoryRepository,
        memory_writer: MemoryWriter,
        memory_retriever: MemoryRetriever,
        routing_logger: RoutingLoggerProtocol,
        tool_executor: Optional[ToolExecutor] = None,
    ) -> None:
        self.normalizer = normalizer
        self.identity_resolver = identity_resolver
        self.surface_policy = surface_policy
        self.router = router
        self.session_manager = session_manager
        self.persona_registry = persona_registry
        self.agent_runtime = agent_runtime
        self.risk_classifier = risk_classifier
        self.approval_manager = approval_manager
        self.memory_repo = memory_repo
        self.memory_writer = memory_writer
        self.memory_retriever = memory_retriever
        self.routing_logger = routing_logger
        self.tool_executor = tool_executor or ToolExecutor(
            tool_scope_enforcer=ToolScopeEnforcer(),
            risk_classifier=self.risk_classifier,
            approval_manager=self.approval_manager,
        )

    async def process(
        self,
        raw_input: Any,
        surface_type: str = "cli",
        external_user_id: str = "local-user",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Process an inbound message end-to-end asynchronously and produce a Response."""
        # 1. Identity Resolution (A4)
        canonical_user_id = self.identity_resolver.resolve_user(
            surface=surface_type, external_id=external_user_id
        )

        # 2. Event Normalization via Gateway (A3)
        envelope: RequestEnvelope = self.normalizer.normalize(
            raw_input=raw_input,
            surface_type=surface_type,
            user_id=canonical_user_id,
            session_id=session_id,
            metadata=metadata,
        )

        # 3. Surface Policy Evaluation (B1)
        policy_eval = self.surface_policy.evaluate(
            surface_ctx=envelope.surface_context, text=envelope.raw_text
        )

        # 4. Session State Retrieval (B3)
        session_state = await self.session_manager.get_session(envelope.session_id)

        # 5. Cross-Surface Memory Retrieval (E3)
        project_tag = (metadata or {}).get("project_tag") or envelope.metadata.get("project_tag")
        memory_context = await self.memory_retriever.retrieve(
            query=envelope.raw_text,
            user_id=envelope.user_id,
            surface=envelope.surface_context.surface_type,
            limit=3,
            project_tag=project_tag,
        )

        # 6. Routing Decision Synthesis (B2)
        decision: RouteDecision = await self.router.route(
            envelope=envelope,
            session_state=session_state,
            surface_policy=policy_eval,
            memory_context=memory_context,
        )

        # 7. Transparency Logging & Explanation (F1)
        self.routing_logger.emit_log(
            decision,
            extra={
                "message_id": envelope.message_id,
                "surface": envelope.surface_context.surface_type,
            },
        )
        routing_explanation = self.routing_logger.render_explanation(decision)

        # 8. Persona Lookup (C1)
        persona = self.persona_registry.get(decision.persona)

        # 9. Agent Runtime Execution (C2) with ToolExecutor returning RuntimeResult
        runtime_result: RuntimeResult = await self.agent_runtime.execute(
            envelope=envelope,
            decision=decision,
            persona=persona,
            session_history=session_state.history,
            tool_executor=self.tool_executor,
        )

        # Derive Response.status and Response.pending_approval ONLY from RuntimeResult
        status: ResponseStatus = "complete"
        pending_approval = runtime_result.pending_approval

        if pending_approval is not None or any(tr.pending for tr in runtime_result.tool_results):
            status = "pending_approval"
        elif any(tr.denied for tr in runtime_result.tool_results):
            status = "denied"
        elif runtime_result.error is not None:
            status = "error"
        else:
            status = "complete"

        reply_text = runtime_result.reply_text

        # 10. Cross-Surface Memory Persistence (E2)
        await self.memory_writer.write_interaction(
            envelope=envelope,
            decision=decision,
            reply_text=reply_text,
        )

        # 11. Update Session State (B3)
        await self.session_manager.append_turn(
            session_id=envelope.session_id,
            user_text=envelope.raw_text,
            persona=decision.persona,
            reply_text=reply_text,
        )

        return Response(
            reply_text=reply_text,
            persona_used=decision.persona,
            route_decision=decision,
            routing_explanation=routing_explanation,
            session_id=envelope.session_id,
            status=status,
            pending_approval=pending_approval,
            timestamp=datetime.now(timezone.utc),
            metadata={
                "message_id": envelope.message_id,
                "surface_type": surface_type,
                "confidence": decision.confidence,
                "autonomy": decision.autonomy,
            },
        )

    async def stream(
        self,
        raw_input: Any,
        surface_type: str = "cli",
        external_user_id: str = "local-user",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """Stream response chunks for real-time surfaces."""
        resp = await self.process(
            raw_input=raw_input,
            surface_type=surface_type,
            external_user_id=external_user_id,
            session_id=session_id,
            metadata=metadata,
        )
        words = resp.reply_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")


def create_pipeline(
    config_dir: Path | str = "config",
    runtime_override: Optional[str] = None,
    approval_override: Optional[str] = None,
) -> OrchestratorPipeline:
    """Factory helper wiring up components based on pipeline.yaml and models.yaml configurations."""
    cfg_path = Path(config_dir)

    # Register default backends across all registries
    register_all_defaults(cfg_path)

    # 1. Load pipeline.yaml
    pipeline_cfg: Dict[str, Any] = {}
    pipeline_file = cfg_path / "pipeline.yaml"
    if pipeline_file.exists():
        with open(pipeline_file, "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f) or {}
    backends = pipeline_cfg.get("backends", {})

    # 2. Load models.yaml
    models_cfg: Dict[str, Any] = {}
    models_file = cfg_path / "models.yaml"
    if models_file.exists():
        with open(models_file, "r", encoding="utf-8") as f:
            models_cfg = yaml.safe_load(f) or {}

    # Config precedence: pipeline.yaml (if set) -> models.yaml provider (if set) -> "default"
    if _is_set(backends.get("router")):
        router_backend = backends.get("router")
    elif _is_set(models_cfg.get("router", {}).get("provider")):
        router_backend = models_cfg.get("router", {}).get("provider")
    else:
        router_backend = "default"

    if _is_set(runtime_override):
        runtime_backend = runtime_override
    elif _is_set(backends.get("runtime")):
        runtime_backend = backends.get("runtime")
    elif _is_set(models_cfg.get("executor", {}).get("provider")):
        runtime_backend = models_cfg.get("executor", {}).get("provider")
    else:
        runtime_backend = "default"

    if _is_set(approval_override):
        approval_manager_backend = approval_override
    elif _is_set(backends.get("approval_manager")):
        approval_manager_backend = backends.get("approval_manager")
    else:
        approval_manager_backend = "default"

    if _is_set(backends.get("embedding_provider")):
        embedding_backend = backends.get("embedding_provider")
    elif _is_set(models_cfg.get("embedding", {}).get("provider")):
        embedding_backend = models_cfg.get("embedding", {}).get("provider")
    else:
        embedding_backend = "default"

    identity_backend = (
        backends.get("identity_resolver")
        if _is_set(backends.get("identity_resolver"))
        else "default"
    )
    surface_policy_backend = (
        backends.get("surface_policy") if _is_set(backends.get("surface_policy")) else "default"
    )
    memory_store_backend = (
        backends.get("memory_store") if _is_set(backends.get("memory_store")) else "default"
    )
    memory_writer_backend = (
        backends.get("memory_writer") if _is_set(backends.get("memory_writer")) else "default"
    )
    memory_retriever_backend = (
        backends.get("memory_retriever") if _is_set(backends.get("memory_retriever")) else "default"
    )
    session_manager_backend = (
        backends.get("session_manager") if _is_set(backends.get("session_manager")) else "default"
    )
    risk_classifier_backend = (
        backends.get("risk_classifier") if _is_set(backends.get("risk_classifier")) else "default"
    )

    # 3. Resolve backends from registries with logged fallback
    normalizer = DefaultEventNormalizer()
    identity_resolver = _resolve_backend(
        IdentityResolverRegistry, identity_backend, "identity_resolver", "default"
    )

    surfaces_cfg_file = cfg_path / "surfaces.yaml"
    surface_policy = _resolve_backend(
        SurfacePolicyRegistry,
        surface_policy_backend,
        "surface_policy",
        "default",
        config_path=surfaces_cfg_file if surfaces_cfg_file.exists() else None,
    )

    session_manager = _resolve_backend(
        SessionManagerRegistry, session_manager_backend, "session_manager", "default"
    )

    personas_dir = cfg_path / "personas"
    persona_registry = PersonaRegistry(personas_dir=personas_dir if personas_dir.exists() else None)

    router = _resolve_backend(RouterRegistry, router_backend, "router", "default")
    runtime = _resolve_backend(RuntimeRegistry, runtime_backend, "runtime", "default")

    risk_classifier = _resolve_backend(
        RiskClassifierRegistry, risk_classifier_backend, "risk_classifier", "default"
    )
    approval_manager = _resolve_backend(
        ApprovalManagerRegistry, approval_manager_backend, "approval_manager", "default"
    )

    embedding_provider = _resolve_backend(
        EmbeddingProviderRegistry, embedding_backend, "embedding_provider", "default"
    )

    memory_repo = _resolve_backend(
        MemoryStoreRegistry, memory_store_backend, "memory_store", "default"
    )
    memory_writer = _resolve_backend(
        MemoryWriterRegistry,
        memory_writer_backend,
        "memory_writer",
        "default",
        repository=memory_repo,
        embedding_provider=embedding_provider,
    )
    memory_retriever = _resolve_backend(
        MemoryRetrieverRegistry,
        memory_retriever_backend,
        "memory_retriever",
        "default",
        repository=memory_repo,
        embedding_provider=embedding_provider,
    )

    routing_logger = RoutingLogger()

    tool_executor = ToolExecutor(
        tool_scope_enforcer=ToolScopeEnforcer(),
        risk_classifier=risk_classifier,
        approval_manager=approval_manager,
    )

    return OrchestratorPipeline(
        normalizer=normalizer,
        identity_resolver=identity_resolver,
        surface_policy=surface_policy,
        router=router,
        session_manager=session_manager,
        persona_registry=persona_registry,
        agent_runtime=runtime,
        risk_classifier=risk_classifier,
        approval_manager=approval_manager,
        memory_repo=memory_repo,
        memory_writer=memory_writer,
        memory_retriever=memory_retriever,
        routing_logger=routing_logger,
        tool_executor=tool_executor,
    )
