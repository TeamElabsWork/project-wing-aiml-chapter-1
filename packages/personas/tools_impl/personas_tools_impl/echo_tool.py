"""Example 'echo' tool plugin implementation.

Owner: C4
"""

from typing import Any, Dict

from contracts.models import ToolSpec
from personas_tools_core.registry import ToolRegistry

ECHO_TOOL_SPEC = ToolSpec(
    name="echo",
    description="Returns the provided message back to the caller for testing and debugging.",
    parameters_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The message to echo back."},
        },
        "required": ["message"],
    },
    return_schema={
        "type": "object",
        "properties": {
            "echoed": {"type": "string"},
        },
    },
    required_scopes=["basic", "test"],
)


def echo_tool_handler(message: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Echo tool implementation."""
    # TODO (C4 Tools Impl Owner): Add real external tools (e.g. bash, web search,
    # git operations, SQL query runner) in this folder as independent plugins.
    return {"echoed": message, "extra": kwargs}


# Automatically register on import
ToolRegistry.register(ECHO_TOOL_SPEC, echo_tool_handler)
