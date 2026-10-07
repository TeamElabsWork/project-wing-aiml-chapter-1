"""Risk classification for requested tool actions.

Owner: D1
"""

from typing import Protocol

from contracts.models import ActionRequest


class RiskClassifier(Protocol):
    """Protocol for classifying risk level of an ActionRequest."""

    def classify(self, action: ActionRequest) -> str:
        """Return risk level: 'low', 'medium', 'high', or 'critical'."""
        ...


class StubRiskClassifier:
    """Stub risk classifier returning 'low' for all actions."""

    def classify(self, action: ActionRequest) -> str:
        # TODO (D1 Risk Classifier Owner): Implement pattern matching on shell commands,
        # SQL DDL/drop checks, regex on dangerous arguments, or an LLM judge.
        return "low"
