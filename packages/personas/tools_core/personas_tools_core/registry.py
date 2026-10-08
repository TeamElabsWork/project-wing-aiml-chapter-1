"""Tool registration and lookup catalog.

Owner: C3
"""

from typing import Any, Callable, Dict, List, Optional

from contracts.models import ToolSpec

ToolCallable = Callable[..., Any]


class ToolRegistry:
    """Registry maintaining tool implementations and their associated ToolSpec metadata."""

    _tools: Dict[str, ToolCallable] = {}
    _specs: Dict[str, ToolSpec] = {}

    @classmethod
    def register(cls, spec: ToolSpec, func: ToolCallable) -> None:
        cls._tools[spec.name.lower()] = func
        cls._specs[spec.name.lower()] = spec

    @classmethod
    def get(cls, name: str) -> Optional[ToolCallable]:
        return cls._tools.get(name.lower())

    @classmethod
    def get_spec(cls, name: str) -> Optional[ToolSpec]:
        return cls._specs.get(name.lower())

    @classmethod
    def list_specs(cls) -> List[ToolSpec]:
        return list(cls._specs.values())

    @classmethod
    def reset(cls) -> None:
        cls._tools.clear()
        cls._specs.clear()

    @classmethod
    def register_defaults(cls) -> None:
        try:
            from personas_tools_impl.echo_tool import register_default_tools

            register_default_tools()
        except ImportError:
            pass
