# ADR-002: In-Memory Component Registries for Swappable Modules

## Status
Accepted

## Context
Modules such as Routers, Agent Runtimes, Memory Backends, and Tools must be swappable without modifying the core pipeline code. Dependency injection frameworks add unnecessary cognitive overhead to a day-1 scaffold.

## Decision
Use simple, explicit Python class-level registry dictionaries with `.register(name, factory)` and `.get(name, **kwargs)`. Modules self-register default implementations upon import or initialization. The orchestrator chooses implementations based on configuration files (`config/*.yaml`).

## Consequences
- Clean inversion of control without heavyweight frameworks.
- Testing and mocking is straightforward by registering lightweight stubs.
