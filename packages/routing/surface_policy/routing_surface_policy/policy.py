"""Surface policy evaluation driven by YAML configuration.

Owner: B1
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

import yaml
from contracts.models import Autonomy, PolicyEvaluation, SurfaceContext, UrgencyLevel


class SurfacePolicyProtocol(Protocol):
    """Protocol for checking surface-specific constraints and urgency."""

    def evaluate(self, surface_ctx: SurfaceContext, text: str) -> PolicyEvaluation:
        """Evaluate surface policy for the given surface context and message text."""
        ...


class SurfacePolicyEngine:
    """YAML-backed surface policy evaluator that extracts constraints and urgency cues."""

    def __init__(self, config_path: Optional[Path | str] = None) -> None:
        self._config: Dict[str, Any] = {}
        if config_path:
            path = Path(config_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}

        # Default fallback policy in case config file is not passed
        if "surfaces" not in self._config:
            self._config["surfaces"] = {
                "cli": {
                    "interactive": True,
                    "supports_markdown": True,
                    "default_autonomy": "semi",
                    "urgency_keywords": ["urgent", "asap", "emergency"],
                    "max_tokens_budget": 4096,
                },
                "telegram": {
                    "interactive": True,
                    "supports_markdown": False,
                    "default_autonomy": "supervised",
                    "urgency_keywords": ["urgent", "sos", "alert"],
                    "max_tokens_budget": 1024,
                },
                "slack": {
                    "interactive": True,
                    "supports_markdown": True,
                    "default_autonomy": "semi",
                    "urgency_keywords": ["p0", "p1", "incident", "outage"],
                    "max_tokens_budget": 2048,
                },
                "web": {
                    "interactive": True,
                    "supports_markdown": True,
                    "default_autonomy": "semi",
                    "urgency_keywords": ["urgent"],
                    "max_tokens_budget": 4096,
                },
            }

    def evaluate(self, surface_ctx: SurfaceContext, text: str) -> PolicyEvaluation:
        # TODO (B1 Surface Policy Owner): Expand with time-of-day policies,
        # role-based urgency escalations, and multi-tenant quotas.
        stype = surface_ctx.surface_type.lower()
        surface_def = self._config.get("surfaces", {}).get(stype, {})

        urgency_keywords: List[str] = surface_def.get("urgency_keywords", ["urgent", "asap"])
        lowered_text = text.lower()
        is_urgent = any(kw in lowered_text for kw in urgency_keywords) or (
            surface_ctx.urgency_hint in ("high", "urgent")
        )

        urgency: UrgencyLevel = "high" if is_urgent else (surface_ctx.urgency_hint or "normal")
        raw_autonomy = surface_def.get("default_autonomy", "semi")
        valid_autonomies: tuple[Autonomy, ...] = ("full", "semi", "read_only", "supervised")
        default_autonomy: Autonomy = raw_autonomy if raw_autonomy in valid_autonomies else "semi"

        # In emergency/high-urgency cases on mobile/chat, autonomy might be restricted to supervised
        assigned_autonomy: Autonomy = (
            "supervised" if (is_urgent and stype == "telegram") else default_autonomy
        )
        supports_markdown: bool = bool(
            surface_def.get("supports_markdown", surface_ctx.supports_markdown)
        )
        max_tokens_budget: int = int(surface_def.get("max_tokens_budget", 2048))

        return PolicyEvaluation(
            is_urgent=is_urgent,
            urgency=urgency,
            default_autonomy=assigned_autonomy,
            max_tokens_budget=max_tokens_budget,
            supports_markdown=supports_markdown,
            extras={
                "surface_type": stype,
                "urgency_score": 0.9 if is_urgent else 0.1,
            },
        )
