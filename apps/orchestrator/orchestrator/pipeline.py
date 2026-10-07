"""End-to-end orchestration pipeline wiring all modular packages together.

Wires Gateway -> Identity -> Policy -> Router -> Persona -> Runtime -> Safety -> Memory -> RoutingLog.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from contracts.models import RequestEnvelope, Response, RouteDecision
from gateway.normalizer import DefaultEventNormalizer, EventNormalizer
from identity.resolver import IdentityResolver, InMemoryIdentityResolver
from memory_retriever.retriever import MemoryRetriever, StubMemoryRetriever
from memory_store.base import MemoryRepository, MemoryStoreRegistry
from memory_writer.writer import MemoryWriter, StubMemoryWriter
from personas_registry.registry import PersonaRegistry
from personas_runtime.base import AgentRuntime, RuntimeRegistry
from routing_router.base import Router, RouterRegistry
from routing_session.manager import InMemorySessionManager, SessionManager
from routing_surface_policy.policy import SurfacePolicyEngine, SurfacePolicyProtocol
from safety_approval.manager import ApprovalManager, AutoApproveStub
from safety_risk_classifier.classifier import RiskClassifier, StubRiskClassifier
from transparency_routing_log.logger import RoutingLogger, RoutingLoggerProtocol


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

    def process(
        self,
        raw_input: Any,
        surface_type: str = "cli",
        external_user_id: str = "local-user",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Process an inbound message end-to-end and produce a Response."""
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
        session_state = self.session_manager.get_session(envelope.session_id)

        # 5. Cross-Surface Memory Retrieval (E3)
        memory_context = self.memory_retriever.retrieve(
            query=envelope.raw_text,
            user_id=envelope.user_id,
            surface=envelope.surface_context.surface_type,
            limit=3,
        )

        # 6. Routing Decision Synthesis (B2)
        decision: RouteDecision = self.router.route(
            envelope=envelope,
            session_state=session_state,
            surface_policy=policy_eval,
            memory_context=memory_context,
        )

        # 7. Persona Lookup (C1)
        persona = self.persona_registry.get(decision.persona)

        # 8. Agent Runtime Execution (C2)
        reply_text = self.agent_runtime.execute(
            envelope=envelope,
            decision=decision,
            persona=persona,
            session_history=session_state.get("history", []),
        )

        # 9. Cross-Surface Memory Persistence (E2)
        self.memory_writer.write_interaction(
            envelope=envelope,
            decision=decision,
            reply_text=reply_text,
        )

        # 10. Update Session State (B3)
        self.session_manager.append_turn(
            session_id=envelope.session_id,
            user_text=envelope.raw_text,
            persona=decision.persona,
            reply_text=reply_text,
        )

        # 11. Transparency Explanation Rendering (F1)
        routing_explanation = self.routing_logger.render_explanation(decision)

        return Response(
            reply_text=reply_text,
            persona_used=decision.persona,
            route_decision=decision,
            routing_explanation=routing_explanation,
            session_id=envelope.session_id,
            timestamp=datetime.now(timezone.utc),
            metadata={
                "message_id": envelope.message_id,
                "surface_type": surface_type,
                "confidence": decision.confidence,
                "autonomy": decision.autonomy,
            },
        )


def create_pipeline(config_dir: Path | str = "config") -> OrchestratorPipeline:
    """Factory helper wiring up the default components and configurations."""
    cfg_path = Path(config_dir)

    # Load models config if available to inspect chosen router / runtime slots
    models_cfg: Dict[str, Any] = {}
    models_file = cfg_path / "models.yaml"
    if models_file.exists():
        with open(models_file, "r", encoding="utf-8") as f:
            models_cfg = yaml.safe_load(f) or {}

    router_backend = models_cfg.get("router", {}).get("provider", "mock")
    if router_backend == "unset":
        router_backend = "mock"

    # Instantiate modules using interfaces and registries
    normalizer = DefaultEventNormalizer()
    identity_resolver = InMemoryIdentityResolver()

    surfaces_cfg_file = cfg_path / "surfaces.yaml"
    surface_policy = SurfacePolicyEngine(
        config_path=surfaces_cfg_file if surfaces_cfg_file.exists() else None
    )

    session_manager = InMemorySessionManager()

    personas_dir = cfg_path / "personas"
    persona_registry = PersonaRegistry(personas_dir=personas_dir if personas_dir.exists() else None)

    router = RouterRegistry.get(router_backend)
    runtime = RuntimeRegistry.get("echo")

    risk_classifier = StubRiskClassifier()
    approval_manager = AutoApproveStub()

    memory_repo = MemoryStoreRegistry.get("in_memory")
    memory_writer = StubMemoryWriter(memory_repo)
    memory_retriever = StubMemoryRetriever(memory_repo)

    routing_logger = RoutingLogger()

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
    )
