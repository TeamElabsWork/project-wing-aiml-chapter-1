import json
from types import SimpleNamespace
from typing import Any

from transparency_routing_log.formatters import format_markdown, format_terminal
from transparency_routing_log.logger import RoutingLogger

ARGS: dict[str, Any] = dict(
    persona="coder", reasoning="code intent detected", autonomy="semi", confidence=0.95
)


def _decision() -> Any:
    return SimpleNamespace(**ARGS, tool_scope=["echo"])


def test_terminal_plain_has_no_ansi() -> None:
    out = format_terminal(**ARGS, color=False)
    assert "\033[" not in out
    assert out.startswith("Summoned coder because")


def test_terminal_color_has_ansi() -> None:
    assert "\033[" in format_terminal(**ARGS, color=True)


def test_markdown_bolds_persona() -> None:
    assert "**coder**" in format_markdown(**ARGS)


def test_render_explanation_unchanged() -> None:
    assert RoutingLogger().render_explanation(_decision()) == (
        "Summoned coder because code intent detected (autonomy: semi, confidence: 0.95)"
    )


def test_render_for_surface_routes_formats() -> None:
    logger = RoutingLogger()
    assert "**coder**" in logger.render_for_surface(_decision(), "slack")
    assert logger.render_for_surface(_decision(), "unknown").startswith("Summoned coder")


def test_structured_log_has_correlation_id() -> None:
    record = json.loads(RoutingLogger().emit_log(_decision()))
    assert len(record["correlation_id"]) == 32
    assert record["event"] == "routing_decision"


def test_correlation_id_can_be_supplied() -> None:
    record = json.loads(RoutingLogger().emit_log(_decision(), extra={"correlation_id": "req-1"}))
    assert record["correlation_id"] == "req-1"
