import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.models import RouteDecision
from transparency_routing_log.formatters import (
    format_markdown,
    format_slack,
    format_terminal,
)
from transparency_routing_log.logger import RoutingLogger

ARGS: dict[str, Any] = dict(
    persona="coder", reasoning="code intent detected", autonomy="semi", confidence=0.95
)


def _decision() -> RouteDecision:
    return RouteDecision(**ARGS, tool_scope=["echo"], urgency="low")


def test_terminal_plain_has_no_ansi() -> None:
    out = format_terminal(**ARGS, color=False)
    assert "\033[" not in out
    assert out.startswith("Summoned coder because")


def test_terminal_color_has_ansi() -> None:
    assert "\033[" in format_terminal(**ARGS, color=True)


def test_markdown_bolds_persona() -> None:
    assert "**coder**" in format_markdown(**ARGS)


def test_slack_uses_single_asterisk_bold() -> None:
    out = format_slack(**ARGS)
    assert "*coder*" in out
    assert "**coder**" not in out


def test_render_explanation_unchanged() -> None:
    assert RoutingLogger().render_explanation(_decision()) == (
        "Summoned coder because code intent detected (autonomy: semi, confidence: 0.95)"
    )


def test_render_for_surface_slack_and_web() -> None:
    logger = RoutingLogger()
    assert "*coder*" in logger.render_for_surface(_decision(), "slack")
    assert "**coder**" not in logger.render_for_surface(_decision(), "slack")
    assert "**coder**" in logger.render_for_surface(_decision(), "web")


def test_render_for_surface_telegram_and_unknown_are_plain() -> None:
    logger = RoutingLogger()
    plain = logger.render_explanation(_decision())
    assert logger.render_for_surface(_decision(), "telegram") == plain
    assert logger.render_for_surface(_decision(), "unknown") == plain


def test_structured_log_has_correlation_id() -> None:
    record = json.loads(RoutingLogger().emit_log(_decision()))
    assert len(record["correlation_id"]) == 32
    assert record["event"] == "routing_decision"


def test_correlation_id_can_be_supplied() -> None:
    record = json.loads(RoutingLogger().emit_log(_decision(), extra={"correlation_id": "req-1"}))
    assert record["correlation_id"] == "req-1"


def test_emit_log_survives_non_serializable_extra() -> None:
    extra = {"when": datetime.now(timezone.utc), "id": uuid.uuid4(), "path": Path("a/b")}
    record = json.loads(RoutingLogger().emit_log(_decision(), extra=extra))
    assert isinstance(record["when"], str)
    assert isinstance(record["id"], str)
    assert isinstance(record["path"], str)
