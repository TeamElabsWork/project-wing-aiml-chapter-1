# ADR-003: Vendor-Agnostic LLM Provider Interface

## Status
Accepted

## Context
The team has not yet decided on which LLM provider (OpenAI, Anthropic, Google Gemini, local models) to adopt. Introducing proprietary SDKs (e.g. `openai`, `anthropic`) locks in dependencies prematurely.

## Decision
Define a minimal `LLMProvider` Protocol containing only two core methods:
- `complete(prompt, system, ...)`
- `structured(prompt, schema, system, ...)`

Provide only a `MockLLMProvider` implementation for day-1 scaffold and tests. `config/models.yaml` sets `provider: "unset"`.

## Consequences
- Zero external LLM vendor SDK dependencies in the initial repository.
- Team members can implement concrete providers when needed by adhering to the protocol.
