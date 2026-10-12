"""Passthrough ContextBuilder implementation.

Owner IDs: C2 (Runtime Owner) + E3 (Memory Owner)
"""

from typing import Any, List, Optional

from contracts.models import (
    ContextBundle,
    MemoryNode,
    Persona,
    PolicyEvaluation,
    RequestEnvelope,
    RouteDecision,
    SessionState,
    ToolSpec,
)


class PassthroughContextBuilder:
    """Default no-op context builder stub passing through raw inputs.

    Preserves full session history and retrieved memories without truncation or summarization,
    calculates crude len//4 estimated token counts, and scopes tool specs to decision.tool_scope.

    Owner IDs: C2 + E3
    """

    def __init__(self, tool_registry: Optional[Any] = None) -> None:
        self.tool_registry = tool_registry

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
        # TODO (C2/E3 owners): trimming, summarization, memory ranking, repo context retrieval
        # TODO (C2 Runtime Owner): Implement sliding window history trimming and token budget enforcement
        # TODO (E3 Memory Owner): Implement memory relevance re-ranking and repo context retrieval

        # 1. Resolve permitted ToolSpecs allowed by decision.tool_scope
        tool_specs: List[ToolSpec] = []
        allowed_tool_names = {name.lower() for name in decision.tool_scope}

        # Check explicitly provided specs in kwargs first
        candidate_specs: Optional[List[ToolSpec]] = kwargs.get("tool_specs") or kwargs.get(
            "available_tools"
        )

        if candidate_specs is not None:
            tool_specs = [
                spec for spec in candidate_specs if spec.name.lower() in allowed_tool_names
            ]
        else:
            registry = self.tool_registry
            if registry is None:
                try:
                    from personas_tools_core.registry import ToolRegistry

                    registry = ToolRegistry
                except ImportError:
                    registry = None

            if registry is not None:
                for name in decision.tool_scope:
                    spec = registry.get_spec(name)
                    if spec is not None:
                        tool_specs.append(spec)

        # 2. Assembled textual contents for crude token estimation (len//4)
        assembled_parts: List[str] = [
            persona.system_prompt,
            envelope.raw_text,
        ]
        for turn in session_state.history:
            assembled_parts.append(str(turn))
        for mem in memory:
            assembled_parts.append(mem.summary)
        for spec in tool_specs:
            assembled_parts.append(spec.name)
            assembled_parts.append(spec.description)

        total_text = "".join(assembled_parts)
        estimated_tokens = len(total_text) // 4

        return ContextBundle(
            persona_prompt=persona.system_prompt,
            history=list(session_state.history),
            memory=list(memory),
            tool_specs=tool_specs,
            token_budget=policy.max_tokens_budget,
            estimated_tokens=estimated_tokens,
            dropped_items=0,
            notes=[],
        )
