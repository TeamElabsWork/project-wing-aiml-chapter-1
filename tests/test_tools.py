"""Comprehensive unit tests for ToolScopeEnforcer, GitHub PR tool, doc lookup, and web search."""

import io
import json
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from contracts.models import ActionRequest, RouteDecision, ToolCall, ToolResult
from personas_tools_core.enforcer import ToolScopeEnforcer
from personas_tools_core.executor import ToolExecutor
from personas_tools_core.registry import ToolRegistry
from personas_tools_impl.echo_tool import (
    doc_lookup_handler,
    github_pr_handler,
    register_default_tools,
    web_search_handler,
)
from safety_approval.manager import AutoApproveStub
from safety_risk_classifier.classifier import StubRiskClassifier


@pytest.fixture(autouse=True)
def setup_tools() -> Generator[None, None, None]:
    ToolRegistry.reset()
    register_default_tools()
    yield
    ToolRegistry.reset()


# ---------------------------------------------------------------------------
# 1. ToolScopeEnforcer Tests
# ---------------------------------------------------------------------------


def test_tool_scope_enforcer_exact_and_case_insensitive() -> None:
    enforcer = ToolScopeEnforcer()
    assert enforcer.is_allowed("echo", ["echo"]) is True
    assert enforcer.is_allowed("Echo", ["echo"]) is True
    assert enforcer.is_allowed("echo", ["ECHO"]) is True
    assert enforcer.is_allowed("github_pr", ["github_pr"]) is True


def test_tool_scope_enforcer_blocks_unauthorized_tools() -> None:
    enforcer = ToolScopeEnforcer()
    assert enforcer.is_allowed("destructive_wipe", ["echo", "github_pr"]) is False
    assert enforcer.is_allowed("github_pr", ["echo"]) is False
    assert enforcer.is_allowed("", ["*"]) is False
    assert enforcer.is_allowed("   ", ["*"]) is False

    action = ActionRequest(
        call_id="call-deny",
        tool_name="destructive_wipe",
        arguments={},
        caller_persona="coder",
    )
    with pytest.raises(PermissionError) as exc_info:
        enforcer.enforce(action, ["echo"])
    assert "not permitted by active tool scope" in str(exc_info.value)


def test_tool_scope_enforcer_wildcard_all() -> None:
    enforcer = ToolScopeEnforcer()
    assert enforcer.is_allowed("echo", ["*"]) is True
    assert enforcer.is_allowed("github_pr", ["*"]) is True
    assert enforcer.is_allowed("destructive_wipe", ["*"]) is True
    assert enforcer.is_allowed("doc_lookup", ["*"]) is True


def test_tool_scope_enforcer_glob_patterns() -> None:
    enforcer = ToolScopeEnforcer()
    # 'git:*' and 'git*' should match git tools
    assert enforcer.is_allowed("github_pr", ["git*"]) is True
    assert enforcer.is_allowed("github_pr", ["git:*"]) is True
    assert enforcer.is_allowed("git:commit", ["git:*"]) is True
    assert enforcer.is_allowed("echo", ["git:*"]) is False

    # 'doc:*' and 'doc*' should match doc tools
    assert enforcer.is_allowed("doc_lookup", ["doc*"]) is True
    assert enforcer.is_allowed("doc_lookup", ["doc:*"]) is True
    assert enforcer.is_allowed("web_search", ["doc:*"]) is False

    # 'web*' should match web_search
    assert enforcer.is_allowed("web_search", ["web*"]) is True
    assert enforcer.is_allowed("web_search", ["web:*"]) is True


def test_tool_scope_enforcer_matches_required_scopes() -> None:
    enforcer = ToolScopeEnforcer()
    # github_pr has required_scopes: ["git", "pr", "github_pr"]
    assert enforcer.is_allowed("github_pr", ["git"]) is True
    assert enforcer.is_allowed("github_pr", ["pr"]) is True

    # doc_lookup has required_scopes: ["doc", "docs", "search", "doc_lookup"]
    assert enforcer.is_allowed("doc_lookup", ["search"]) is True
    assert enforcer.is_allowed("doc_lookup", ["docs"]) is True


# ---------------------------------------------------------------------------
# 2. GitHub PR Tool Tests
# ---------------------------------------------------------------------------


def test_github_pr_offline_simulation_defaults() -> None:
    result = github_pr_handler(title="Automated PR")
    assert result["pr_number"] == 42
    assert "github.com" in result["html_url"]
    assert result["title"] == "Automated PR"
    assert result["status"] == "opened"
    assert result["mode"] == "simulated_offline"
    assert result["branch"].startswith("feat/pr-")
    assert result["base"] == "main"
    assert result["commit_sha"].startswith("sha-")


def test_github_pr_offline_simulation_custom_parameters() -> None:
    result = github_pr_handler(
        title="Add authentication middleware",
        repo="my-org/my-project",
        branch="feat/auth-middleware",
        patch="diff --git a/auth.py b/auth.py\n+def authenticate(): pass",
        base="develop",
        body="Implements JWT auth middleware.",
    )
    assert result["title"] == "Add authentication middleware"
    assert result["branch"] == "feat/auth-middleware"
    assert result["base"] == "develop"
    assert result["html_url"] == f"https://github.com/my-org/my-project/pull/{result['pr_number']}"
    assert result["status"] == "opened"
    assert "Created branch 'feat/auth-middleware'" in result["summary"]


@patch("urllib.request.urlopen")
def test_github_pr_live_api_integration(mock_urlopen: MagicMock) -> None:
    # Set up mock responses for:
    # 1. Base branch ref SHA lookup
    # 2. Create feature branch ref
    # 3. Create/update patch content
    # 4. Open PR
    base_ref_resp = io.BytesIO(json.dumps({"object": {"sha": "base12345678"}}).encode())
    create_branch_resp = io.BytesIO(b"{}")
    commit_patch_resp = io.BytesIO(json.dumps({"commit": {"sha": "commitabcdef12"}}).encode())
    open_pr_resp = io.BytesIO(
        json.dumps(
            {
                "number": 101,
                "html_url": "https://github.com/TeamElabsWork/project-wing-aiml-chapter-1/pull/101",
            }
        ).encode()
    )

    mock_urlopen.side_effect = [
        base_ref_resp,
        create_branch_resp,
        commit_patch_resp,
        open_pr_resp,
    ]

    with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake_token_for_test"}):
        result = github_pr_handler(
            title="Fix routing bug",
            repo="TeamElabsWork/project-wing-aiml-chapter-1",
            branch="fix/routing-bug",
            patch="+ fixed logic",
            base="main",
        )

    assert result["mode"] == "live_github_api"
    assert result["pr_number"] == 101
    assert (
        result["html_url"]
        == "https://github.com/TeamElabsWork/project-wing-aiml-chapter-1/pull/101"
    )
    assert result["commit_sha"] == "commitabcdef12"
    assert result["branch"] == "fix/routing-bug"
    assert result["base"] == "main"


@patch("urllib.request.urlopen")
def test_github_pr_live_api_fallback_on_error(mock_urlopen: MagicMock) -> None:
    mock_urlopen.side_effect = RuntimeError("Network error")
    with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake_token"}):
        result = github_pr_handler(title="Test PR")
    # Should fall back cleanly to offline simulation without crashing
    assert result["mode"] == "simulated_offline"
    assert result["pr_number"] == 42


# ---------------------------------------------------------------------------
# 3. Doc Lookup & Web Search Tool Tests
# ---------------------------------------------------------------------------


def test_doc_lookup_empty_query() -> None:
    res = doc_lookup_handler(query="   ")
    assert res["total_results"] == 0
    assert "error" in res


def test_doc_lookup_searches_repo_docs() -> None:
    res = doc_lookup_handler(query="architecture", source="docs", top_k=2)
    assert res["query"] == "architecture"
    assert res["source"] == "docs"
    assert res["total_results"] > 0
    first = res["results"][0]
    assert "title" in first
    assert "path_or_url" in first
    assert "snippet" in first


def test_doc_lookup_top_k_limiting() -> None:
    res = doc_lookup_handler(query="surface router", source="docs", top_k=1)
    assert len(res["results"]) <= 1


def test_web_search_handler() -> None:
    res = web_search_handler(query="python asyncio", top_k=2)
    assert res["query"] == "python asyncio"
    assert res["total_results"] > 0
    assert "https://" in res["results"][0]["path_or_url"]


# ---------------------------------------------------------------------------
# 4. End-to-End ToolScopeEnforcer & ToolExecutor Integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_tools_pass_through_scope_enforcer_before_execution() -> None:
    executor = ToolExecutor(
        tool_scope_enforcer=ToolScopeEnforcer(),
        risk_classifier=StubRiskClassifier(),
        approval_manager=AutoApproveStub(),
    )

    # 1. Allowed tool succeeds
    decision_coder = RouteDecision(
        persona="coder",
        tool_scope=["echo", "github_pr", "doc_lookup"],
        autonomy="semi",
        confidence=0.9,
        reasoning="Coder tasks",
    )

    call_echo = ToolCall(
        call_id="c-1",
        tool_name="echo",
        arguments={"message": "hello"},
    )
    res_echo: ToolResult = await executor.execute(call_echo, decision_coder, "coder")
    assert res_echo.ok is True
    assert res_echo.output.get("echoed") == "hello"

    call_pr = ToolCall(
        call_id="c-2",
        tool_name="github_pr",
        arguments={"title": "Refactor router"},
    )
    res_pr: ToolResult = await executor.execute(call_pr, decision_coder, "coder")
    assert res_pr.ok is True
    assert res_pr.output.get("status") == "opened"

    call_doc = ToolCall(
        call_id="c-3",
        tool_name="doc_lookup",
        arguments={"query": "contracts"},
    )
    res_doc: ToolResult = await executor.execute(call_doc, decision_coder, "coder")
    assert res_doc.ok is True
    assert res_doc.output.get("total_results", 0) > 0

    # 2. Blocked tool fails at scope enforcer step
    decision_restricted = RouteDecision(
        persona="coder",
        tool_scope=["echo"],  # only echo
        autonomy="semi",
        confidence=0.9,
        reasoning="Restricted coder",
    )

    call_blocked_pr = ToolCall(
        call_id="c-4",
        tool_name="github_pr",
        arguments={"title": "Unauthorized PR"},
    )
    res_blocked: ToolResult = await executor.execute(call_blocked_pr, decision_restricted, "coder")
    assert res_blocked.ok is False
    assert "not permitted by active tool scope" in (res_blocked.error or "")

    call_blocked_doc = ToolCall(
        call_id="c-5",
        tool_name="doc_lookup",
        arguments={"query": "secret"},
    )
    res_blocked_doc: ToolResult = await executor.execute(
        call_blocked_doc, decision_restricted, "coder"
    )
    assert res_blocked_doc.ok is False
    assert "not permitted by active tool scope" in (res_blocked_doc.error or "")


@pytest.mark.asyncio
async def test_wildcard_scope_allows_tools_in_executor() -> None:
    executor = ToolExecutor(
        tool_scope_enforcer=ToolScopeEnforcer(),
        risk_classifier=StubRiskClassifier(),
        approval_manager=AutoApproveStub(),
    )

    # RouteDecision has 'git:*' scope
    decision_git = RouteDecision(
        persona="coder",
        tool_scope=["git:*", "doc:*"],
        autonomy="semi",
        confidence=0.9,
        reasoning="Wildcard scope",
    )

    call_pr = ToolCall(
        call_id="c-git-1",
        tool_name="github_pr",
        arguments={"title": "PR with git wildcard scope"},
    )
    res_pr: ToolResult = await executor.execute(call_pr, decision_git, "coder")
    assert res_pr.ok is True
    assert res_pr.output.get("status") == "opened"

    call_doc = ToolCall(
        call_id="c-doc-1",
        tool_name="doc_lookup",
        arguments={"query": "ADR"},
    )
    res_doc: ToolResult = await executor.execute(call_doc, decision_git, "coder")
    assert res_doc.ok is True


def test_tool_catalog_all_default_specs_registered() -> None:
    specs = {s.name: s for s in ToolRegistry.list_specs()}
    assert "echo" in specs
    assert "github_pr" in specs
    assert "destructive_wipe" in specs
    assert "doc_lookup" in specs
    assert "web_search" in specs
