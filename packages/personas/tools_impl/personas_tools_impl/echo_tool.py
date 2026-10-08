"""Example tools plugins: echo, github_pr, and destructive_wipe.

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
    required_scopes=["basic", "test", "echo"],
    destructive=False,
    side_effects="none",
    execution_target="any",
)

GITHUB_PR_TOOL_SPEC = ToolSpec(
    name="github_pr",
    description="Proposes code changes by opening a branch and Pull Request via GitHub API per ADR-006.",
    parameters_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository identifier (owner/repo)."},
            "title": {"type": "string", "description": "PR title."},
            "branch": {"type": "string", "description": "Branch name to create."},
            "patch": {"type": "string", "description": "Code patch or summary of changes."},
        },
        "required": ["title"],
    },
    return_schema={
        "type": "object",
        "properties": {
            "pr_number": {"type": "integer"},
            "html_url": {"type": "string"},
        },
    },
    required_scopes=["git", "pr", "github_pr"],
    destructive=False,
    side_effects="external",
    execution_target="remote",
)

DESTRUCTIVE_TOOL_SPEC = ToolSpec(
    name="destructive_wipe",
    description="Simulated destructive tool for verifying safety and approval gates.",
    parameters_schema={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target entity to wipe."},
        },
        "required": ["target"],
    },
    return_schema={
        "type": "object",
        "properties": {
            "wiped": {"type": "boolean"},
        },
    },
    required_scopes=["admin", "destructive_wipe"],
    destructive=True,
    side_effects="write",
    execution_target="local",
)


def echo_tool_handler(message: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Echo tool implementation."""
    return {"echoed": message, "extra": kwargs}


def github_pr_handler(title: str = "Automated PR", **kwargs: Any) -> Dict[str, Any]:
    """Stub GitHub PR tool handler (no external network calls)."""
    return {
        "pr_number": 42,
        "html_url": "https://github.com/TeamElabsWork/project-wing-aiml-chapter-1/pull/42",
        "title": title,
        "status": "opened",
        "extra": kwargs,
    }


def destructive_wipe_handler(target: str = "all", **kwargs: Any) -> Dict[str, Any]:
    """Stub destructive tool handler."""
    return {"wiped": True, "target": target}


def register_default_tools() -> None:
    ToolRegistry.register(ECHO_TOOL_SPEC, echo_tool_handler)
    ToolRegistry.register(GITHUB_PR_TOOL_SPEC, github_pr_handler)
    ToolRegistry.register(DESTRUCTIVE_TOOL_SPEC, destructive_wipe_handler)
