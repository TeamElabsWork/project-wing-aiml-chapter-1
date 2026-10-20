"""Terminal-colored and markdown formatters for routing transparency lines."""

from __future__ import annotations

import os
import sys
import uuid

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"


def new_correlation_id() -> str:
    """Create a fresh ID that ties together all logs of one request."""
    return uuid.uuid4().hex


def _use_color(force: bool | None = None) -> bool:
    """Color only on a real terminal, and never when NO_COLOR is set."""
    if force is not None:
        return force
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _confidence_color(confidence: float) -> str:
    if confidence >= 0.8:
        return _GREEN
    if confidence >= 0.5:
        return _YELLOW
    return _RED


def format_terminal(
    persona: str,
    reasoning: str,
    autonomy: str,
    confidence: float,
    *,
    color: bool | None = None,
) -> str:
    """Colored 'Summoned <persona> because ...' line for terminals."""
    if not _use_color(color):
        return (
            f"Summoned {persona} because {reasoning} "
            f"(autonomy: {autonomy}, confidence: {confidence:.2f})"
        )
    return (
        f"Summoned {_CYAN}{_BOLD}{persona}{_RESET} because {reasoning} "
        f"{_DIM}(autonomy: {autonomy}, {_RESET}"
        f"{_confidence_color(confidence)}confidence: {confidence:.2f}{_RESET}{_DIM}){_RESET}"
    )


def format_markdown(
    persona: str,
    reasoning: str,
    autonomy: str,
    confidence: float,
) -> str:
    """Markdown quote block for Slack, Telegram and web surfaces."""
    return (
        f"> Summoned **{persona}** because {reasoning}\n"
        f"> _autonomy:_ `{autonomy}` · _confidence:_ `{confidence:.2f}`"
    )
