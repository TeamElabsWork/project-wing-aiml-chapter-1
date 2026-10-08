"""Surface policy engine and rules configuration.

Owner: B1
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

import yaml
from contracts.models import Autonomy, PolicyEvaluation, SurfaceContext, UrgencyLevel


class SurfacePolicyProtocol(Protocol):
    """Protocol for assessing surface-specific constraints and urgency signals."""

    def evaluate(self, surface_ctx: SurfaceContext, text: str = "") -> PolicyEvaluation:
        """Evaluate incoming text and surface context into a structured PolicyEvaluation."""
        ...


class SurfacePolicyEngine:
    """Rule engine evaluating surface limits, urgency patterns, and output modes from YAML."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self.config_path = Path(config_path) if config_path else None
        self._surfaces_config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        if self.config_path and self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self._surfaces_config = data.get("surfaces", {})

    def evaluate(self, surface_ctx: SurfaceContext, text: str = "") -> PolicyEvaluation:
        stype = surface_ctx.surface_type.lower()
        surface_def = self._surfaces_config.get(stype, {})

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


class SurfacePolicyRegistry:
    """Registry allowing surface policy engines to be configured and selected."""

    _registry: Dict[str, Callable[..., SurfacePolicyProtocol]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., SurfacePolicyProtocol]) -> None:
        cls._registry[name.lower()] = factory

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> SurfacePolicyProtocol:
        lowered = name.lower()
        if lowered not in cls._registry:
            raise KeyError(
                f"SurfacePolicy '{name}' not found in registry. Registered: {list(cls._registry.keys())}"
            )
        return cls._registry[lowered](**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()

    @classmethod
    def register_defaults(cls, config_path: Optional[Any] = None) -> None:
        cls.register(
            "yaml",
            lambda **kwargs: SurfacePolicyEngine(
                config_path=kwargs.get("config_path", config_path)
            ),
        )
        cls.register(
            "default",
            lambda **kwargs: SurfacePolicyEngine(
                config_path=kwargs.get("config_path", config_path)
            ),
        )
        cls.register(
            "unset",
            lambda **kwargs: SurfacePolicyEngine(
                config_path=kwargs.get("config_path", config_path)
            ),
        )
