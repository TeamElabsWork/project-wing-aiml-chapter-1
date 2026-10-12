# personas-context-builder

Context assembly and token budgeting module for Surface-Aware Agent Orchestration.

Owners: C2 (Runtime Owner) + E3 (Memory Owner)

## Overview
Assembles `ContextBundle` containing:
- Persona instructions
- Multi-turn conversation history
- Retrieved episodic cross-surface memories
- Whitelisted `ToolSpec` definitions allowed by `decision.tool_scope`
- Token budget allocated by the surface policy

Provides `PassthroughContextBuilder` as the default no-op stub while preserving expansion points for trimming, summarization, memory ranking, and repo-context retrieval.
