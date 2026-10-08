"""Risk classification for requested tool actions.

Owner: D1
"""

from typing import Any, Callable, Dict, Optional, Protocol

from contracts.models import ActionRequest, RiskLevel, ToolSpec


class RiskClassifier(Protocol):
    """Protocol for classifying risk level of an ActionRequest."""

    def classify(self, action: ActionRequest, spec: Optional[ToolSpec] = None) -> RiskLevel:
        """Return risk level: 'low', 'medium', 'high', or 'critical'."""
        ...


class StubRiskClassifier:
    """Stub risk classifier inspecting action and ToolSpec properties."""

    def classify(self, action: ActionRequest, spec: Optional[ToolSpec] = None) -> RiskLevel:
        # TODO (D1 Risk Classifier Owner): Implement pattern matching on shell commands,
        # SQL DDL/drop checks, regex on dangerous arguments, or an LLM judge.
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
        cls.register("default", lambda **kwargs: StubRiskClassifier())


RiskClassifierRegistry.register_defaults()
