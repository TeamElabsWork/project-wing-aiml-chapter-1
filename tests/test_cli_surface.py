"""Unit tests for the CLI surface adapter (A2).

Covers configuration loading, local tool execution, and prompt session creation.
All tests run offline with no external dependencies per CONTRIBUTING.md guidelines.
"""

import json
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

import pytest
from contracts.models import Response, RouteDecision, TokenUsage
from surface_cli.repl import CLIAdapter, CLIConfig, load_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_response(
    reply_text: str = "hello",
    persona: str = "coder",
    metadata: Optional[dict[str, Any]] = None,
) -> Response:
    """Build a minimal Response for testing render_response / local tool dispatch."""
    return Response(
        reply_text=reply_text,
        persona_used=persona,
        route_decision=RouteDecision(
            persona=persona,
            confidence=0.9,
            reasoning="test",
        ),
        routing_explanation="Summoned coder because test",
        session_id="test-session",
        status="complete",
        usage=TokenUsage(),
        metadata=metadata or {},
    )


class _StubPipeline:
    """Minimal stub satisfying PipelineRunner for unit tests."""

    async def process(
        self,
        raw_input: Any,
        surface_type: str = "cli",
        external_user_id: str = "cli-user",
        session_id: str | None = None,
    ) -> Response:
        return _make_response(reply_text=f"echo: {raw_input}")


# ---------------------------------------------------------------------------
# Config loading tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for load_config() reading ~/.surface-agent/config.json."""

    def test_missing_file_returns_empty_config(self, tmp_path: Path) -> None:
        fake_config = tmp_path / "config.json"
        with patch("surface_cli.repl.CONFIG_FILE", fake_config):
            cfg = load_config()
        assert cfg.api_endpoint == ""
        assert cfg.auth_token == ""
        assert cfg.user_id == ""

    def test_valid_config_loaded(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "api_endpoint": "https://api.example.com",
                    "auth_token": "tok_secret123",
                    "user_id": "dev-alice",
                }
            ),
            encoding="utf-8",
        )
        with patch("surface_cli.repl.CONFIG_FILE", config_file):
            cfg = load_config()
        assert cfg.api_endpoint == "https://api.example.com"
        assert cfg.auth_token == "tok_secret123"
        assert cfg.user_id == "dev-alice"

    def test_malformed_json_returns_empty_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json!!", encoding="utf-8")
        with patch("surface_cli.repl.CONFIG_FILE", config_file):
            cfg = load_config()
        assert cfg.api_endpoint == ""
        assert cfg.user_id == ""

    def test_non_dict_json_returns_empty_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text('"just a string"', encoding="utf-8")
        with patch("surface_cli.repl.CONFIG_FILE", config_file):
            cfg = load_config()
        assert cfg.api_endpoint == ""

    def test_partial_config_fills_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"api_endpoint": "http://localhost:8000"}),
            encoding="utf-8",
        )
        with patch("surface_cli.repl.CONFIG_FILE", config_file):
            cfg = load_config()
        assert cfg.api_endpoint == "http://localhost:8000"
        assert cfg.auth_token == ""
        assert cfg.user_id == ""


class TestCLIConfig:
    """Tests for CLIConfig.get() convenience accessor."""

    def test_get_existing_field(self) -> None:
        cfg = CLIConfig(user_id="alice")
        assert cfg.get("user_id") == "alice"

    def test_get_missing_field_returns_default(self) -> None:
        cfg = CLIConfig()
        assert cfg.get("user_id", "fallback") == "fallback"

    def test_get_empty_string_returns_default(self) -> None:
        cfg = CLIConfig(user_id="")
        assert cfg.get("user_id", "local-developer") == "local-developer"


# ---------------------------------------------------------------------------
# Local tool execution tests
# ---------------------------------------------------------------------------


class TestLocalToolExecution:
    """Tests for CLIAdapter.execute_local_tool()."""

    def test_read_file_handler(self, tmp_path: Path) -> None:
        target = tmp_path / "example.txt"
        target.write_text("file contents here", encoding="utf-8")

        adapter = CLIAdapter(pipeline=_StubPipeline())
        result = adapter.execute_local_tool("read_file", {"path": str(target)})
        assert result == "file contents here"

    def test_unknown_tool_returns_error(self) -> None:
        adapter = CLIAdapter(pipeline=_StubPipeline())
        result = adapter.execute_local_tool("nonexistent_tool", {})
        assert "No local handler registered" in result
        assert "nonexistent_tool" in result

    def test_handler_exception_returns_error(self) -> None:
        adapter = CLIAdapter(pipeline=_StubPipeline())
        result = adapter.execute_local_tool("read_file", {"path": "/no/such/file/ever"})
        assert "Local execution failed" in result


# ---------------------------------------------------------------------------
# CLIAdapter integration tests
# ---------------------------------------------------------------------------


class TestCLIAdapterConfig:
    """Tests for config integration in CLIAdapter."""

    def test_adapter_loads_config_on_init(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"user_id": "dev-bob"}),
            encoding="utf-8",
        )
        with patch("surface_cli.repl.CONFIG_FILE", config_file):
            adapter = CLIAdapter(pipeline=_StubPipeline())
        assert adapter.config.user_id == "dev-bob"

    @pytest.mark.asyncio
    async def test_send_message_uses_config_user_id(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"user_id": "dev-charlie"}),
            encoding="utf-8",
        )

        captured: dict[str, Any] = {}

        class _CapturePipeline:
            async def process(
                self,
                raw_input: Any,
                surface_type: str = "cli",
                external_user_id: str = "cli-user",
                session_id: str | None = None,
            ) -> Response:
                captured["external_user_id"] = external_user_id
                return _make_response()

        with patch("surface_cli.repl.CONFIG_FILE", config_file):
            adapter = CLIAdapter(pipeline=_CapturePipeline())

        await adapter.send_message_async("hello")
        assert captured["external_user_id"] == "dev-charlie"

    @pytest.mark.asyncio
    async def test_send_message_defaults_user_id_when_no_config(self, tmp_path: Path) -> None:
        fake_config = tmp_path / "config.json"  # does not exist on disk
        captured: dict[str, Any] = {}

        class _CapturePipeline:
            async def process(
                self,
                raw_input: Any,
                surface_type: str = "cli",
                external_user_id: str = "cli-user",
                session_id: str | None = None,
            ) -> Response:
                captured["external_user_id"] = external_user_id
                return _make_response()

        with patch("surface_cli.repl.CONFIG_FILE", fake_config):
            adapter = CLIAdapter(pipeline=_CapturePipeline())

        await adapter.send_message_async("hello")
        assert captured["external_user_id"] == "local-developer"


# ---------------------------------------------------------------------------
# Render response with local tool actions
# ---------------------------------------------------------------------------


class TestRenderLocalToolActions:
    """Tests for local tool dispatch in render_response()."""

    def test_render_executes_local_tool_actions(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        target = tmp_path / "data.txt"
        target.write_text("payload", encoding="utf-8")

        response = _make_response(
            metadata={
                "local_tool_actions": [
                    {"tool_name": "read_file", "arguments": {"path": str(target)}},
                ]
            },
        )

        adapter = CLIAdapter(pipeline=_StubPipeline())
        adapter.render_response(response)

        captured = capsys.readouterr().out
        assert "[LOCAL TOOL]" in captured
        assert "payload" in captured

    def test_render_skips_when_no_local_actions(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = _make_response()
        adapter = CLIAdapter(pipeline=_StubPipeline())
        adapter.render_response(response)

        captured = capsys.readouterr().out
        assert "[LOCAL TOOL]" not in captured


# ---------------------------------------------------------------------------
# Prompt session creation
# ---------------------------------------------------------------------------


class TestPromptSession:
    """Tests for _create_prompt_session graceful fallback."""

    def test_returns_none_when_prompt_toolkit_unavailable(self) -> None:
        adapter = CLIAdapter(pipeline=_StubPipeline())
        with patch("surface_cli.repl.HAS_PROMPT_TOOLKIT", False):
            session = adapter._create_prompt_session()
        assert session is None

    def test_creates_session_when_prompt_toolkit_available(self, tmp_path: Path) -> None:
        adapter = CLIAdapter(pipeline=_StubPipeline())
        with patch("surface_cli.repl.CONFIG_DIR", tmp_path):
            session = adapter._create_prompt_session()
        # When prompt_toolkit is installed, we should get a PromptSession
        if session is not None:
            assert hasattr(session, "prompt")
