"""Surface policy engine and rules configuration.

Owner: B1
"""

import logging
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, cast

import yaml
from contracts.models import Autonomy, PolicyEvaluation, SurfaceContext, UrgencyLevel

logger = logging.getLogger(__name__)


class SurfacePolicyProtocol(Protocol):
    """Protocol for assessing surface-specific constraints and urgency signals."""

    def evaluate(self, surface_ctx: SurfaceContext, text: str = "") -> PolicyEvaluation:
        """Evaluate incoming text and surface context into a structured PolicyEvaluation."""
        ...


def _parse_time(val: Any) -> Optional[time]:
    """Parse time string in HH:MM or HH:MM:SS format into a datetime.time object."""
    if isinstance(val, time):
        return val
    if isinstance(val, str):
        parts = val.strip().split(":")
        if len(parts) >= 2:
            try:
                hour = int(parts[0])
                minute = int(parts[1])
                second = int(parts[2]) if len(parts) > 2 else 0
                return time(hour=hour, minute=minute, second=second)
            except ValueError:
                return None
    return None


def _normalize_urgency_level(level: Optional[str]) -> UrgencyLevel:
    """Ensure urgency level maps to valid UrgencyLevel ('low', 'normal', 'high')."""
    if level in ("urgent", "high"):
        return "high"
    if level == "low":
        return "low"
    return "normal"


def _parse_autonomy(val: Any) -> Optional[Autonomy]:
    """Parse and validate an autonomy value."""
    if val in ("full", "semi", "read_only", "supervised"):
        return cast(Autonomy, val)
    return None


def _is_in_time_window(current_t: time, start_t: time, end_t: time) -> bool:
    """Check if current_t falls within [start_t, end_t), handling overnight spans."""
    if start_t > end_t:
        # Overnight span, e.g. 18:00 to 08:00
        return current_t >= start_t or current_t < end_t
    else:
        # Same-day span, e.g. 09:00 to 17:00
        return start_t <= current_t < end_t


class SurfacePolicyEngine:
    """Rule engine evaluating surface limits, urgency patterns, and output modes from YAML."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self.config_path: Optional[Path] = Path(config_path) if config_path else None
        self._surfaces_config: Dict[str, Any] = {}
        self._config_mtime: Optional[float] = None
        self._last_reload_time: Optional[datetime] = None
        self._load_config()

    def _load_config(self) -> bool:
        """Load YAML configuration from disk if available. Returns True if successfully loaded."""
        if not self.config_path:
            return False
        try:
            if not self.config_path.exists():
                return False
            current_mtime = self.config_path.stat().st_mtime
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._surfaces_config = data.get("surfaces", {})
            self._config_mtime = current_mtime
            self._last_reload_time = datetime.now(timezone.utc)
            return True
        except Exception as exc:
            logger.warning(
                "Failed to load surface policy config from %s: %s",
                self.config_path,
                exc,
            )
            return False

    def _maybe_reload_config(self) -> bool:
        """Check if config file mtime has changed on disk and reload if needed."""
        if not self.config_path:
            return False
        try:
            if not self.config_path.exists():
                return False
            current_mtime = self.config_path.stat().st_mtime
            if self._config_mtime is None or current_mtime != self._config_mtime:
                return self._load_config()
        except OSError:
            pass
        return False

    def reload(self) -> bool:
        """Explicitly reload configuration from disk."""
        return self._load_config()

    @property
    def config_mtime(self) -> Optional[float]:
        """Return the last modified time of the loaded configuration file."""
        return self._config_mtime

    def evaluate(
        self,
        surface_ctx: SurfaceContext,
        text: str = "",
        now: Optional[datetime] = None,
    ) -> PolicyEvaluation:
        # Step 1: Hot-reload config if changed on disk
        was_reloaded = self._maybe_reload_config()

        stype = surface_ctx.surface_type.lower()
        surface_def = self._surfaces_config.get(stype, {})

        # Step 2: Keyword and hint-based urgency detection
        urgency_keywords: List[str] = surface_def.get("urgency_keywords", ["urgent", "asap"])
        lowered_text = text.lower()
        keyword_matched = any(kw.lower() in lowered_text for kw in urgency_keywords)
        hint_is_urgent = surface_ctx.urgency_hint in ("high", "urgent")
        base_urgent = keyword_matched or hint_is_urgent

        # Step 3: Time-based urgency rules evaluation
        eval_now = now or datetime.now().astimezone()
        current_time = eval_now.time()
        is_weekend = eval_now.weekday() >= 5  # Saturday=5, Sunday=6

        time_rules = surface_def.get("time_urgency_rules") or {}
        time_escalation_applied = False
        time_reason: Optional[str] = None
        time_escalate_to: Optional[UrgencyLevel] = None

        # Check after-hours rule
        ah_rule = time_rules.get("after_hours")
        if isinstance(ah_rule, dict):
            start_t = _parse_time(ah_rule.get("start", "18:00"))
            end_t = _parse_time(ah_rule.get("end", "08:00"))
            if start_t and end_t and _is_in_time_window(current_time, start_t, end_t):
                # Check if rule conditions apply
                ah_keywords = ah_rule.get("keywords")
                matches_ah_keywords = bool(
                    ah_keywords and any(kw.lower() in lowered_text for kw in ah_keywords)
                )
                if ah_rule.get("all_messages", False) or matches_ah_keywords or base_urgent:
                    time_escalation_applied = True
                    time_reason = "after_hours"
                    target_level = ah_rule.get("escalate_to", "high")
                    if target_level in ("low", "normal", "high", "urgent"):
                        time_escalate_to = target_level

        # Check weekend rule
        wk_rule = time_rules.get("weekends")
        if is_weekend and wk_rule:
            wk_dict = wk_rule if isinstance(wk_rule, dict) else {}
            wk_keywords = wk_dict.get("keywords")
            matches_wk_keywords = bool(
                wk_keywords and any(kw.lower() in lowered_text for kw in wk_keywords)
            )
            if wk_dict.get("all_messages", False) or matches_wk_keywords or base_urgent:
                time_escalation_applied = True
                time_reason = "weekend"
                target_level = wk_dict.get("escalate_to", "high")
                if target_level in ("low", "normal", "high", "urgent"):
                    time_escalate_to = target_level

        # Determine overall urgency
        is_urgent = base_urgent or time_escalation_applied
        urgency: UrgencyLevel
        if is_urgent:
            if time_escalate_to:
                urgency = _normalize_urgency_level(time_escalate_to)
            elif surface_ctx.urgency_hint:
                urgency = _normalize_urgency_level(surface_ctx.urgency_hint)
            else:
                urgency = "high"
        else:
            urgency = _normalize_urgency_level(surface_ctx.urgency_hint)

        # Step 4: Autonomy restriction based on YAML config and surface type
        raw_autonomy = surface_def.get("default_autonomy", "semi")
        default_autonomy: Autonomy = _parse_autonomy(raw_autonomy) or "semi"

        restriction_cfg = surface_def.get("autonomy_restriction")
        restriction_default: Optional[Autonomy] = None
        restriction_on_urgent: Optional[Autonomy] = None

        if isinstance(restriction_cfg, str):
            parsed_r = _parse_autonomy(restriction_cfg)
            restriction_default = parsed_r
            restriction_on_urgent = parsed_r
        elif isinstance(restriction_cfg, dict):
            restriction_default = _parse_autonomy(restriction_cfg.get("default"))
            restriction_on_urgent = _parse_autonomy(restriction_cfg.get("on_urgent"))

        # Recommend autonomy restrictions based on surface type (e.g., mobile = supervised)
        channel = (surface_def.get("metadata") or {}).get("channel", "")
        is_mobile = stype in ("telegram", "mobile", "mobile_chat") or channel in (
            "mobile",
            "mobile_chat",
        )

        base_autonomy: Autonomy
        if restriction_default is not None:
            base_autonomy = restriction_default
        elif is_mobile and default_autonomy not in ("read_only", "supervised"):
            base_autonomy = "supervised"
        else:
            base_autonomy = default_autonomy

        assigned_autonomy: Autonomy
        if is_urgent:
            if restriction_on_urgent is not None:
                assigned_autonomy = restriction_on_urgent
            elif is_mobile:
                assigned_autonomy = "supervised"
            else:
                assigned_autonomy = base_autonomy
        else:
            assigned_autonomy = base_autonomy

        supports_markdown: bool = bool(
            surface_def.get("supports_markdown", surface_ctx.supports_markdown)
        )

        # Step 5: Dynamic token budget adjustments
        base_tokens_budget: int = int(surface_def.get("max_tokens_budget", 2048))
        dynamic_budget = surface_def.get("dynamic_budget") or {}
        max_tokens_budget: int = base_tokens_budget
        budget_policy = "default"

        if isinstance(dynamic_budget, dict):
            if is_urgent and "urgent" in dynamic_budget:
                max_tokens_budget = int(dynamic_budget["urgent"])
                budget_policy = "urgent_dynamic_budget"
            elif time_escalation_applied and "after_hours" in dynamic_budget:
                max_tokens_budget = int(dynamic_budget["after_hours"])
                budget_policy = "after_hours_dynamic_budget"

        return PolicyEvaluation(
            is_urgent=is_urgent,
            urgency=urgency,
            default_autonomy=assigned_autonomy,
            max_tokens_budget=max_tokens_budget,
            supports_markdown=supports_markdown,
            extras={
                "surface_type": stype,
                "urgency_score": 0.9 if is_urgent else 0.1,
                "keyword_matched": keyword_matched,
                "time_escalation_applied": time_escalation_applied,
                "time_reason": time_reason,
                "autonomy_restriction_applied": (
                    assigned_autonomy != default_autonomy or (restriction_cfg is not None)
                ),
                "recommended_autonomy": assigned_autonomy,
                "budget_policy": budget_policy,
                "config_reloaded": was_reloaded,
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
