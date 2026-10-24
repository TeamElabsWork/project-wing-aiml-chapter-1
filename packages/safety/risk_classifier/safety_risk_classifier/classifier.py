"""Risk classification for requested tool actions.

Owner: D1
"""

import re
from typing import Any, Callable, Dict, List, Optional, Protocol

from contracts.models import ActionRequest, RiskLevel, ToolSpec

# ---------------------------------------------------------------------------
# Dangerous-argument pattern lists used by RuleBasedRiskClassifier
# ---------------------------------------------------------------------------

CRITICAL_ARG_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"--force\b", re.IGNORECASE),
    re.compile(r"--hard\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
    re.compile(r"\bwipe\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[cCdDeE]:", re.IGNORECASE),
]

HIGH_ARG_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"--no-verify\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(r"\breset\b", re.IGNORECASE),
    re.compile(r"\bdestroy\b", re.IGNORECASE),
]

MEDIUM_ARG_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\bpush\b", re.IGNORECASE),
    re.compile(r"\bmerge\b", re.IGNORECASE),
    re.compile(r"\bdeploy\b", re.IGNORECASE),
    re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE),
]

# Tool-name keywords (fallback when no spec metadata is available)
CRITICAL_NAME_KEYWORDS = ("delete", "drop", "destroy", "wipe", "rm", "truncate")
HIGH_NAME_KEYWORDS = ("reset", "rollback", "revert")
MEDIUM_NAME_KEYWORDS = ("write", "update", "patch", "pr", "push", "merge", "deploy")


class RiskClassifier(Protocol):
    """Protocol for classifying risk level of an ActionRequest."""

    def classify(self, action: ActionRequest, spec: Optional[ToolSpec] = None) -> RiskLevel:
        """Return risk level: 'low', 'medium', 'high', or 'critical'."""
        ...


class StubRiskClassifier:
    """Stub risk classifier inspecting action and ToolSpec properties."""

    def classify(self, action: ActionRequest, spec: Optional[ToolSpec] = None) -> RiskLevel:
        if spec:
            if spec.destructive:
                return "critical"
            if spec.side_effects in ("write", "external"):
                return "medium"

        # Check action name hints
        lower_name = action.tool_name.lower()
        if any(w in lower_name for w in ("delete", "drop", "destroy", "wipe", "rm")):
            return "critical"
        if any(w in lower_name for w in ("write", "update", "patch", "pr", "push")):
            return "medium"

        return "low"


def _flatten_arguments(arguments: Dict[str, Any]) -> str:
    """Flatten all argument values into a single searchable string."""
    parts: List[str] = []
    for value in arguments.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            parts.extend(str(v) for v in value)
        else:
            parts.append(str(value))
    return " ".join(parts)


def _scan_patterns(text: str, patterns: List[re.Pattern[str]]) -> bool:
    """Return True if any compiled pattern matches inside *text*."""
    return any(p.search(text) for p in patterns)


class RuleBasedRiskClassifier:
    """Rule-based risk classifier inspecting tool name AND command arguments.

    Checks ToolSpec metadata first (destructive flag, side_effects), then scans
    the stringified arguments for known dangerous patterns (``--force``, ``DROP TABLE``,
    ``rm -rf``, ``sudo``, etc.), and finally falls back to tool-name keyword matching.
    The highest risk level found across all checks wins.
    """

    def classify(self, action: ActionRequest, spec: Optional[ToolSpec] = None) -> RiskLevel:
        # Accumulate detected risk tiers; return the highest.
        risk: RiskLevel = "low"

        # --- Phase 1: ToolSpec metadata ---
        if spec:
            if spec.destructive:
                return "critical"  # short-circuit: always critical
            if spec.side_effects in ("write", "external"):
                risk = "medium"

        # --- Phase 2: Argument-content scanning ---
        args_text = _flatten_arguments(action.arguments)

        if _scan_patterns(args_text, CRITICAL_ARG_PATTERNS):
            return "critical"
        if _scan_patterns(args_text, HIGH_ARG_PATTERNS):
            risk = _max_risk(risk, "high")
        if _scan_patterns(args_text, MEDIUM_ARG_PATTERNS):
            risk = _max_risk(risk, "medium")

        # --- Phase 3: Tool-name keyword fallback ---
        lower_name = action.tool_name.lower()
        if any(w in lower_name for w in CRITICAL_NAME_KEYWORDS):
            risk = _max_risk(risk, "critical")
        elif any(w in lower_name for w in HIGH_NAME_KEYWORDS):
            risk = _max_risk(risk, "high")
        elif any(w in lower_name for w in MEDIUM_NAME_KEYWORDS):
            risk = _max_risk(risk, "medium")

        return risk


# Ordering constant for risk comparison
_RISK_ORDER: Dict[RiskLevel, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    """Return the higher of two risk levels."""
    return a if _RISK_ORDER[a] >= _RISK_ORDER[b] else b


class RiskClassifierRegistry:
    """Registry allowing risk classifiers to be selected via config."""

    _registry: Dict[str, Callable[..., RiskClassifier]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., RiskClassifier]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> RiskClassifier:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"RiskClassifier '{name}' not found in registry. Registered classifiers: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls) -> None:
        cls.register("stub", lambda **kwargs: StubRiskClassifier())
        cls.register("rule_based", lambda **kwargs: RuleBasedRiskClassifier())
        cls.register("default", lambda **kwargs: RuleBasedRiskClassifier())
        cls.register("unset", lambda **kwargs: RuleBasedRiskClassifier())
